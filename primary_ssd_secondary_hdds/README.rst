Mixing SSDs and HDDs the smart way
==================================

Introduction
------------

Suppose there are N OSD nodes with 1 SSD and 1 HDD, and a replicated pool
with the number of copies being 3. We'd like to store one copy on an SSD
(to improve the read performance), and two others -- on HDDs. Also all
copies should reside on different hosts to avoid service interruption
(and/or data loss) if one of the nodes goes down (gets broken).

It's easy to implement SSD-only and HDD-only pools: basically one moves SSD
and HDD backed OSDs to different roots. That is, if the initial hierarchy is::

  root <- host_n <- [ SSD_n, HDD_n, HDD_{n+1}]

the reordered one is::

  ssd_root <- ssd_host_n <- [SSD_n]
  hdd_root <- hdd_host_n <- [HDD_n, HDD_{n+1}]

However some failure domain information has been lost while reordering
the hierarchy: nothing says that "SSD X and HDD Y reside on the same host"
any more, so nothing prevents CRUSH from putting 2 copies of data to
the same host.

Thinking outside of the box
---------------------------

Let's introduce two new bucket types: ``disktype`` and ``cell``. There are
N ``cell`` buckets (matching the OSD nodes' number), and each ``cell``
contains two ``disktype`` buckets: ``disktype_n_ssd`` and ``disktype_n_hdd``.
``disktype_n_ssd`` bucket contains SSD backed OSDs residing on node #n,
and the ``disktype_n_hdd`` bucket contains HDD backed OSDs residing on
all nodes *except* node #n::

  .                   _ disktype_n_ssd <- ssd_host_n 
  .                  / 
  . root <- cell_n <
  .                  \_ disktype_n_hdd <- [hdd_host_m, m != n]


Actual CRUSH map
------------------

Here it is::

        # begin crush map
        tunable choose_local_tries 0
        tunable choose_local_fallback_tries 0
        tunable choose_total_tries 50
        tunable chooseleaf_descend_once 1
        tunable straw_calc_version 1

        # devices
        device 0 osd.0
        device 1 osd.1
        device 2 osd.2
        device 3 osd.3
        device 4 osd.4
        device 5 osd.5

        # types
        type 0 osd
        type 1 host
        # should be unused in the original CRUSH map
        type 2 disktype
        # should be unused in the original CRUSH map
        type 3 cell
        type 4 chassis
        type 5 rack
        type 6 row
        type 7 pdu
        type 8 pod
        type 9 room
        type 10 datacenter
        type 11 region
        type 12 root

        # the original CRUSH entries start here

        # buckets
        host saceph-osd2 {
                id -2		# do not change unnecessarily
                # weight 1.999
                alg straw
                hash 0	# rjenkins1
                item osd.0 weight 0.999
                item osd.3 weight 0.999
        }
        host saceph-osd1 {
                id -3		# do not change unnecessarily
                # weight 1.999
                alg straw
                hash 0	# rjenkins1
                item osd.1 weight 0.999
                item osd.5 weight 0.999
        }
        host saceph-osd3 {
                id -4		# do not change unnecessarily
                # weight 1.999
                alg straw
                hash 0	# rjenkins1
                item osd.2 weight 0.999
                item osd.4 weight 0.999
        }

        root default {
                id -1		# do not change unnecessarily
                # weight 5.997
                alg straw
                hash 0	# rjenkins1
                item saceph-osd2 weight 1.999
                item saceph-osd1 weight 1.999
                item saceph-osd3 weight 1.999
        }

        rule replicated_ruleset {
                ruleset 0
                type replicated
                min_size 2
                max_size 3
                step take default
                step chooseleaf firstn 0 type host
                step emit
        }

        # the original CRUSH entries end here

        host saceph-osd2-ssd {
                id -20		# do not change unnecessarily
                alg straw
                hash 0	# rjenkins1
                item osd.0 weight 0.999
        }

        host saceph-osd2-hdd {
                id -19		# do not change unnecessarily
                alg straw
                hash 0	# rjenkins1
                item osd.3 weight 0.999
        }

        host saceph-osd3-hdd {
                id -18		# do not change unnecessarily
                alg straw
                hash 0	# rjenkins1
                item osd.4 weight 0.999
        }

        host saceph-osd3-ssd {
                id -17		# do not change unnecessarily
                alg straw
                hash 0	# rjenkins1
                item osd.2 weight 0.999
        }

        host saceph-osd1-ssd {
                id -16		# do not change unnecessarily
                alg straw
                hash 0	# rjenkins1
                item osd.1 weight 0.999
        }

        host saceph-osd1-hdd {
                id -15		# do not change unnecessarily
                # weight 1.999
                alg straw
                hash 0	# rjenkins1
                item osd.5 weight 0.999
        }

        disktype hdd-cell-3 {
                id -14
                alg straw
                hash 0
                item saceph-osd1-hdd weight 0.999
                item saceph-osd2-hdd weight 0.999
        }

        disktype ssd-cell-3 {
                id -13
                alg straw
                hash 0
                item saceph-osd3-ssd weight 0.999
        }

        disktype ssd-cell-2 {
                id -11
                alg straw
                hash 0
                item saceph-osd2-ssd weight 0.999
        }

        disktype hdd-cell-2 {
                id -12
                alg straw
                hash 0
                item saceph-osd1-hdd weight 0.999
                item saceph-osd3-hdd weight 0.999
        }

        disktype ssd-cell-1 {
                id -9
                alg straw
                hash 0
                item saceph-osd1-ssd weight 0.999
        }

        disktype hdd-cell-1 {
                id -10
                alg straw
                hash 0
                item saceph-osd2-hdd weight 0.999
                item saceph-osd3-hdd weight 0.999
        }

        cell cell-3 {
                id -8
                alg straw
                hash 0
                item ssd-cell-3 weight 0.999
                item hdd-cell-3 weight 1.999
        }

        cell cell-2 {
                id -7
                alg straw
                hash 0
                item ssd-cell-2 weight 0.999
                item hdd-cell-2 weight 1.999
        }

        cell cell-1 {
                id -6
                alg straw
                hash 0
                item ssd-cell-1 weight 0.999
                item hdd-cell-1 weight 1.999
        }

        root ssdhdd {
                id -5		# do not change unnecessarily
                alg straw
                hash 0	# rjenkins1
                item cell-1 weight 2.999
                item cell-2 weight 2.999
                item cell-3 weight 2.999
        }

        # rules
        rule ssd_hdd_rule {
                ruleset 1
                type replicated
                min_size 1
                max_size 10
                step take ssdhdd
                step choose firstn 1 type cell
                step choose firstn 2 type disktype
                step chooseleaf firstn 2 type host
                step emit
        }

        # end crush map

Let's compile and activate the new CRUSH map::

  crushtool -c ssd_hdd_crush.txt -o ssd_hdd_crush.bin
  ceph osd setcrushmap -i ssd_hdd_crush.bin

and check if OSDs are correctly assigned to placement groups::

  python check_pg_duplicate_hosts.py

Now one can set the primary affinity of non-SSD OSDs to 0, and start using
the cluster.

