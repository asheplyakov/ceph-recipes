#!/usr/bin/env python

import os
import re
import stat
import subprocess
import sys

from optparse import OptionParser


def guess_first_partition_size_offset(img):
    out = subprocess.check_output(['sudo', 'kpartx', '-l', img])
    # loop0p1 : 0 4192256 /dev/loop0 2048
    # loop deleted : /dev/loop0
    first_part_txt = out.split('\n')[0].strip()
    # loop0p1 : 0 4192256 /dev/loop0 2048
    part, _, start_s, end_s, bdev, offset_s = first_part_txt.split()
    size = int(end_s) - int(start_s)
    return size, int(offset_s)


def resize2fs(bdev, *args):
    cmd = ['resize2fs']
    cmd.extend(args)
    cmd.append(bdev)
    subprocess.check_call(cmd)


def run_e2fsck(bdev, *args):
    cmd = ['e2fsck']
    cmd.extend(args)
    cmd.append(bdev)
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        good_retcodes = (
            0,  # everything is OK
            1,  # errors have been fixed
        )
        if e.returncode not in good_retcodes:
            raise


def clone_rootfs(dst, img=None, offset=0):
    cmd = ['e2image', '-p', '-aro', str(offset * 512), img, dst]
    subprocess.check_call(cmd)
    run_e2fsck(dst, '-f', '-p')
    resize2fs(dst, '-p')
    run_e2fsck(dst, '-f', '-p', '-D')


def rbd_unmap(bdev):
    if stat.S_ISLNK(os.lstat(bdev).st_mode):
       bdev = os.path.abspath(bdev)
    subprocess.check_call(['rbd', 'unmap', bdev])


def is_qcow2(img):
    try:
        subprocess.check_call(['qemu-img', 'info', '-f', 'qcow2', img])
        return True
    except subprocess.CalledProcessError:
        return False


def div_round_up(a, b):
    n = a / b
    if (a % b) != 0:
        n += 1
    return n


class FastRBDImport(object):
    def __init__(self, src_img,
                 dst_name=None,
                 size=None, pool='rbd', image_features=3,
                 user='admin', keyring=None):
        self._src_img = src_img
        self._pool = pool
        if dst_name is None:
            dst_name = os.path.basename(src_img)
        self._dst_name = dst_name
        self._size = size
        self._image_features = image_features
        self._user = user
        if keyring is None:
            keyring = '/etc/ceph/ceph.client.%s.keyring' % user
        self._keyring = keyring
        self._src_virt_size = None

    def _conv2raw(self):
        if is_qcow2(self._src_img):
            tmp_img = re.sub("\.qcow2", "", self._src_img) + ".raw"
            subprocess.check_call(['qemu-img', 'convert', '-f', 'qcow2',
                                   '-O', 'raw', self._src_img, tmp_img])
        else:
            tmp_img = self._src_img

        raw_size = os.stat(tmp_img).st_size
        if self._size < raw_size:
            self._size = raw_size
        return tmp_img

    def _make_empty_rbd_img(self):
        cmd = ['rbd', 'create', '--image-format', '2',
               '--image-features', str(self._image_features),
               '--size', str(div_round_up(self._size, 1024 * 1024)),
               '%s/%s' % (self._pool, self._dst_name)]
        subprocess.check_call(cmd)

    def _map_rbd_img(self):
        subprocess.check_call(['rbd', 'map',
                               '--id', self._user,
                               '--keyring', self._keyring,
                               '%s/%s' % (self._pool, self._dst_name)])
        return '/dev/rbd/%s/%s' % (self._pool, self._dst_name)

    def run(self):
        tmp_img = self._conv2raw()
        self._make_empty_rbd_img()
        bdev = self._map_rbd_img()
        fs_size, offset = guess_first_partition_size_offset(tmp_img)
        clone_rootfs(bdev, img=tmp_img, offset=offset)
        rbd_unmap(bdev)


def main():
    parser = OptionParser()
    parser.add_option('-s', '--size', type=int, dest='size', default=0,
                      help='rbd image size in bytes')
    parser.add_option('-u', '--id', dest='user', default='admin',
                      help='ceph user ID (without leading "client.")')
    parser.add_option('-k', '--keyring', dest='keyring',
                      help='ceph keyring to authenticate with')
    parser.add_option('-p', '--pool', dest='pool', default='rbd',
                      help='destination RADOS pool')
    parser.add_option('-d', '--dst-img', dest='dst_name',
                      help='destination image name')
    parser.add_option('-f', '--image-features', type=int, dest='image_features',
                      default=3, help='rbd image features')
    options, args = parser.parse_args()
    if len(args) != 1:
        print("Source image name must be specified")
        sys.exit(1)
    imp = FastRBDImport(args[0],
                        dst_name=options.dst_name,
                        pool=options.pool,
                        keyring=options.keyring,
                        user=options.user,
                        size=options.size)
    imp.run()


if __name__ == '__main__':
    main()
