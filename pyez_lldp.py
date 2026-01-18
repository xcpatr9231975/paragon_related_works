from jnpr.junos import Device
from jnpr.junos.op.lldp import LLDPNeighborTable
import json

def dump_junos_lldp_database(host, user, password):
    dev = Device(host=host, user=user, password=password, port=22)
    dev.open()
    lldp_table = LLDPNeighborTable(dev)
    lldp_table.get()
    neighbors = []
    for neighbor in lldp_table:
        neighbors.append({
            'local_int': neighbor.local_int,
            'remote_chassis_id': neighbor.remote_chassis_id,
            'remote_port_desc': neighbor.remote_port_desc,
            'remote_sysname': neighbor.remote_sysname,
        })
    dev.close()
    return neighbors

# Example usage
if __name__ == '__main__':
    lldp_data = dump_junos_lldp_database('10.161.32.178', 'jnpr', 'pass123')
    print(json.dumps(lldp_data, indent=2))
