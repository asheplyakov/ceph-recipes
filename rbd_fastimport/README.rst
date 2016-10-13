Import ext[234] images into rbd faster
======================================

Purpose
-------

Import ext[234] (root) filesystem image from a Debian/Ubuntu/CentOS
cloud image into rbd

Usage
-----

To import the root filesystem from Ubuntu cloud image::

  ./rbd_fastimport.py -s 16 -d trusty-server-cloudimg-amd64-disk1.img.rootfs trusty-server-cloudimg-amd64-disk1.img


This

* creates 16GB `trusty-server-cloudimg-amd64-disk1.img.rootfs` image in the `rbd` pool
* clones the root filesystem from the `trusty-server-cloudimg-amd64-disk1.img` qcow2
  image into that rbd image
* resizes the root filesystem to occupy the whole rbd image


Why?
----

`rbd import` works just fine, however it's a bit slower (rbd tool is not aware of
ext[234] filesystem structure and copies unallocated space), and you have to 
manually convert qcow2 to raw, guess the 1st partition offset, resize the imported
rbd image, etc.

