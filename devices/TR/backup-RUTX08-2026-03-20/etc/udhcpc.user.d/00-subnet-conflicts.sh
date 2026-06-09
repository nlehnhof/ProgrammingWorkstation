#!/bin/sh
. /lib/functions/network.sh

check_subnets() {
        local ip mask
        network_get_subnet dest "$1"
        ip="$(echo "$dest" | cut -d/ -f1)"
        mask="$(echo "$dest" | cut -d/ -f2)"

        local ip_int mask_int sn_start sn_end
        ip_int=$(ip2int "$ip")
        mask_int=$(mask2int "$mask")
        sn_start=$(( ip_int & mask_int ))
        sn_end=$(( sn_start | (~mask_int & 0xFFFFFFFF) ))

        local IFS=$'\n'

        for interface in $(ubus -S call network.interface dump | jsonfilter -e "@.interface[@.interface != \"$1\"][\"ipv4-address\"][0]"); do
                local ifaddr ifmask ifaddr_int ifmask_int if_sn_start if_sn_end

                ifaddr=$(echo "$interface" | jsonfilter -e '@.address')
                ifmask=$(echo "$interface" | jsonfilter -e '@.mask')

                ifaddr_int=$(ip2int "$ifaddr")
                ifmask_int=$(mask2int "$ifmask")
                if_sn_start=$(( ifaddr_int & ifmask_int ))
                if_sn_end=$(( if_sn_start | (~ifmask_int & 0xFFFFFFFF) ))

                [ $sn_start -le $if_sn_end ] && [ $if_sn_start -le $sn_end ] && {
                        ubus send vuci.notify '{"event": "subnet_conflict"}'
                        return
                }
        done


}

ip2int() {
        local i1 i2 i3 i4
        local IFS=.

        read -r i1 i2 i3 i4 <<EOF
$1
EOF
        unset IFS
        echo "$(( (i1 << 24) + (i2 << 16) + (i3 << 8) + i4 ))"
}

mask2int() {
        echo $(( 0xFFFFFFFF << (32 - $1) & 0xFFFFFFFF ))
}

if [ "$1" = "renew" ] || [ "$1" = "bound" ]; then
        check_subnets "$INTERFACE"
fi
