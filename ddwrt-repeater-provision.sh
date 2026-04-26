#!/bin/sh
set -eu

# DD-WRT repeater provisioner for the working routed design on the R6800.
#
# Current target state:
# - 5 GHz uplink client on wlan1 to VentureCompound-5
# - Uplink IP 192.168.1.131/24 with gateway 192.168.1.1
# - Local LAN/AP on br0 at 192.168.10.1/24
# - Local DHCP on 192.168.10.0/24
# - Local AP SSID VentureCompound-garage on 2.4 GHz
# - NAT from br0 out wlan1
# - SSH and syslog enabled
#
# This script intentionally avoids stopservice/startservice churn. It writes
# NVRAM, commits, and finishes with one clean reboot.

UPLINK_IF="wlan1"
UPLINK_IP="192.168.1.131"
UPLINK_NETMASK="255.255.255.0"
UPLINK_GW="192.168.1.1"
UPLINK_DNS="192.168.1.1 1.1.1.1"

LAN_IP="192.168.10.1"
LAN_NETMASK="255.255.255.0"
LAN_DHCP_START="192.168.10.64"
LAN_DHCP_COUNT="190"
LAN_DHCP_LEASE="1440"

LOCAL_SSID="VentureCompound-garage"
LOCAL_PSK="Kingsley1028!"
UPLINK_SSID="VentureCompound-5"
UPLINK_PSK="Kingsley1028!"

AUTHORIZED_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDdNPzm6J+s2IkaCKYQ+puCJxIN0ONK37UxL05lEbTD8xEHl6SivXKsr1tZ2yaZOcJZ42CFqFkFlIiTAAOXf021Q1whdYLT2ZG7IOrdaBRuDcm7Pi0Sh0P5uAPhh2+LuUIIA2A0TLl1/8EN2YFEKkWcPH/crL0bnIwGR6n7Omg9aTbJGK4bWMX1VpDw4pXts0N1KL6YXv41DFnYe67hpbW4AFmJp2pReTZ243tkVQhtchI5tAFxpakWpLWtPM/uQK3llKo8E3LQJEsn8WKWmFP00SmIdQYpoH9DKFZ2/8O/mdbw2ysWXMHUMKNDgSiUy3hKxt7Wi1PBVtWSuxfE+B17GANOPsiATDitg0QN5qov43HUUAOrLc02t4okegZ4W+XN/rJxZP0Y80zOHJPC6d2fOTzDTU1XI6dtjrxfdEmUADL+yimNujd6qlDCGOF2NIEAhd/f6Wxsrpldaeb6jJMn5I5qOcZv4f/Hq6UtAjDz/CQhcoxP844k7PPMMOx+Apk= adrian@adrian-laptop"

set_nvram() {
  nvram set "$1=$2"
}

echo "Configuring uplink"
set_nvram router_name "generic-repeater"
set_nvram wk_mode "gateway"
set_nvram wan_proto "dhcp"
set_nvram wan_ifname "$UPLINK_IF"
set_nvram wan_iface "$UPLINK_IF"
set_nvram wan_ifnames "$UPLINK_IF"
set_nvram wan_ipaddr "$UPLINK_IP"
set_nvram wan_netmask "$UPLINK_NETMASK"
set_nvram wan_gateway "$UPLINK_GW"
set_nvram wan_dns "$UPLINK_DNS"

echo "Configuring local LAN"
set_nvram lan_proto "static"
set_nvram lan_ipaddr "$LAN_IP"
set_nvram lan_netmask "$LAN_NETMASK"
set_nvram lan_gateway "0.0.0.0"
set_nvram sv_localdns "$LAN_IP"
set_nvram lan_ifname "br0"
set_nvram lan_ifnames "vlan1 vlan2 wlan0"

echo "Configuring DHCP/DNS"
set_nvram dnsmasq_enable "1"
set_nvram dns_dnsmasq "1"
set_nvram auth_dnsmasq "0"
set_nvram local_dns "1"
set_nvram dhcpfwd_enable "0"
set_nvram dhcpd_usenvram "1"
set_nvram dhcp_start "$LAN_DHCP_START"
set_nvram dhcp_num "$LAN_DHCP_COUNT"
set_nvram dhcp_lease "$LAN_DHCP_LEASE"
set_nvram dnsmasq_options "dhcp-option=6,192.168.1.1,1.1.1.1"

echo "Configuring management"
set_nvram sshd_enable "1"
set_nvram sshd_passwd_auth "1"
set_nvram sshd_port "22"
set_nvram sshd_forwarding "0"
set_nvram sshd_authorized_keys "$AUTHORIZED_KEY"
set_nvram telnetd_enable "0"
set_nvram http_enable "0"
set_nvram https_enable "0"
set_nvram remote_management "0"
set_nvram remote_mgt_https "0"
set_nvram remote_mgt_telnet "0"

echo "Configuring logging"
set_nvram log_enable "1"
set_nvram syslogd_enable "1"
set_nvram klogd_enable "1"
set_nvram syslogd_rem_ip ""
set_nvram ttraff_enable "0"
set_nvram rflow_enable "0"
set_nvram ntp_enable "1"
set_nvram time_zone "US/Eastern"

echo "Configuring 2.4 GHz local AP"
set_nvram wl0_mode "ap"
set_nvram wlan0_mode "ap"
set_nvram wl0_ssid "$LOCAL_SSID"
set_nvram wlan0_ssid "$LOCAL_SSID"
set_nvram wl0_channel "9"
set_nvram wlan0_channel "9"
set_nvram wl0_nbw "20"
set_nvram wlan0_nbw "20"
set_nvram wl0_nctrlsb "none"
set_nvram wlan0_nctrlsb "none"
set_nvram wl0_crypto "aes"
set_nvram wl0_akm "psk2"
set_nvram wl0_auth "0"
set_nvram wl0_auth_mode "none"
set_nvram wl0_wpa_psk "$LOCAL_PSK"
set_nvram wlan0_security_mode "wpa"
set_nvram wlan0_akm "psk2"
set_nvram wlan0_auth_mode "none"
set_nvram wlan0_psk2 "1"
set_nvram wlan0_psk2-sha256 "0"
set_nvram wlan0_ccmp "1"
set_nvram wlan0_ccmp-256 "0"
set_nvram wlan0_gcmp "0"
set_nvram wlan0_gcmp-256 "0"
set_nvram wlan0_tkip "0"
set_nvram wlan0_wpa_psk "$LOCAL_PSK"

echo "Configuring 5 GHz uplink"
set_nvram wl1_mode "sta"
set_nvram wlan1_mode "sta"
set_nvram wl1_ssid "$UPLINK_SSID"
set_nvram wlan1_ssid "$UPLINK_SSID"
set_nvram wl1_channel "165"
set_nvram wlan1_channel "165"
set_nvram wl1_nbw "20"
set_nvram wlan1_nbw "20"
set_nvram wl1_nctrlsb "none"
set_nvram wlan1_nctrlsb "none"
set_nvram wl1_crypto "aes"
set_nvram wl1_akm "psk2"
set_nvram wl1_auth "0"
set_nvram wl1_auth_mode "none"
set_nvram wl1_wpa_psk "$UPLINK_PSK"
set_nvram wlan1_security_mode "wpa"
set_nvram wlan1_akm "psk2"
set_nvram wlan1_auth_mode "none"
set_nvram wlan1_psk2 "1"
set_nvram wlan1_psk2-sha256 "0"
set_nvram wlan1_ccmp "1"
set_nvram wlan1_ccmp-256 "0"
set_nvram wlan1_gcmp "0"
set_nvram wlan1_gcmp-256 "0"
set_nvram wlan1_tkip "0"
set_nvram wlan1_wpa_psk "$UPLINK_PSK"

echo "Configuring persistent startup/firewall"
set_nvram rc_startup 'sleep 10
ifconfig br0 192.168.10.1 netmask 255.255.255.0 up
brctl addif br0 vlan1 >/dev/null 2>&1 || true
brctl addif br0 vlan2 >/dev/null 2>&1 || true
brctl addif br0 wlan0 >/dev/null 2>&1 || true
brctl delif br0 wlan1 >/dev/null 2>&1 || true
ifconfig wlan1 192.168.1.131 netmask 255.255.255.0 up >/dev/null 2>&1 || true
route del default >/dev/null 2>&1 || true
route add default gw 192.168.1.1 dev wlan1 >/dev/null 2>&1 || true'

set_nvram rc_firewall 'iptables -t nat -C POSTROUTING -o wlan1 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -o wlan1 -j MASQUERADE
iptables -C FORWARD -i br0 -o wlan1 -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i br0 -o wlan1 -j ACCEPT
iptables -C FORWARD -i wlan1 -o br0 -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i wlan1 -o br0 -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -C INPUT -i br0 -p tcp --dport 22 -s 192.168.10.0/24 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i br0 -p tcp --dport 22 -s 192.168.10.0/24 -j ACCEPT
iptables -C INPUT -i wlan1 -p tcp --dport 22 -s 192.168.1.0/24 -d 192.168.1.131 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i wlan1 -p tcp --dport 22 -s 192.168.1.0/24 -d 192.168.1.131 -j ACCEPT'

echo "Committing NVRAM"
nvram commit

echo "Rebooting cleanly"
reboot
