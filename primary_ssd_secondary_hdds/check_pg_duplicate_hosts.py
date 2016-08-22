#!/usr/bin/env python
# encoding: utf-8
# Fail if any PG has replicas on the same host

import json
import subprocess


def find_children_by_type(tree, node, node_type):
    children = (child for child in tree if child['id'] in node['children'])
    for child in children:
        if child['type'] == node_type:
            yield child
        else:
            find_children_by_type(tree, child, node_type)


def devices_by_host(root='default'):
    raw = subprocess.check_output(['sudo',
                                   'ceph', 'osd', 'tree', '--format=json'])
    osdtree = json.loads(raw.strip())['nodes']
    root_node = [node for node in osdtree
                 if node['type'] == 'root' and node['name'] == root][0]
    osd_hosts = find_children_by_type(osdtree, root_node, 'host')
    osds_by_host = dict((int(osd), node['name'])
                        for node in osd_hosts
                        for osd in node.get('children', []))
    return osds_by_host


def pg_stats():
    raw = subprocess.check_output(['sudo',
                                   'ceph', 'pg', 'dump', '--format=json'])
    return json.loads(raw.strip())['pg_stats']


def pgs_have_duplicate_hosts():
    osds_by_host = devices_by_host(root='default')

    def has_duplicate_hosts(pg):
        hosts = list(osds_by_host[osd] for osd in pg['acting'])
        uniq_hosts = set(hosts)
        return list(sorted(uniq_hosts)) != list(sorted(hosts))

    broken_pgs = dict((pg['pgid'], tuple(pg['acting']))
                      for pg in pg_stats() if has_duplicate_hosts(pg))
    return len(broken_pgs) != 0, broken_pgs


def main():
    result, broken_pgs = pgs_have_duplicate_hosts()
    if result:
        print(json.dumps(broken_pgs, sort_keys=True, indent=2))
        raise RuntimeError('PGs have copies on the same host')


if __name__ == '__main__':
    main()
