#!/usr/bin/env python3

"""
MPLS Scale Generator - Large-Scale IPv4 Install-Route Support

- Reads YAML describing routers, MPLS, LSP templates, and LSP groups
- Generates per-router Junos "set" configs using Jinja2
- Supports large sequential IPv4 destination-prefix ranges WITHOUT listing thousands of routes
- Output: one file per router in an output directory (default: mpls_configs/)

Features:
  • Sequential IPv4 prefix generation (no need to list 3000 routes in YAML)
  • Linear or cyclic IP distribution modes
  • Per-LSP or batched install-route assignment
  • IP pool management for LSP source addresses
  • Organized output directory (mpls_configs/ by default)
  • Clean, production-ready configurations

Usage:
    python mpls_scale_generator.py ultimate_multi_routers_1127.yaml
    python mpls_scale_generator.py ultimate_multi_routers_1127.yaml ./mpls_configs

YAML Configuration Example:

    lsp_groups:
      # Large-scale: sequential /32s without listing all routes
      - name: lsp_group_4
        range: [1501, 4500]              # 3000 LSPs
        destination: 1.1.1.3
        template: high_priority
        install_route_mode: linear       # or 'cyclic'
        install_route_base: 1.2.3.5/32   # Starting IP
        install_route_count: 3000        # Generate 3000 sequential IPs
        install_route_step: 1            # Increment by 1 per IP

      # Small-scale: traditional approach (still works)
      - name: lsp_group_1
        range: [1, 500]
        destination: 1.1.1.1
        template: primary_te
        install_routes:
          - 1.2.3.1/32
          - 1.2.3.2/32
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any, List

import yaml
import ipaddress
from jinja2 import Environment


class MPLSScaleGenerator:
    """
    Generate individual Junos MPLS config files per router using Jinja2,
    including large-scale sequential install-route generation.
    """

    MASTER_MPLS_TEMPLATE = """# ==========================================
# MPLS Configuration for Router: {{ router_name }}
# Generated: {{ timestamp }}
# Group: {{ group_name }}
# ==========================================
{% if mpls %}
# ==================== MPLS BASE CONFIGURATION ====================
set groups {{ group_name }} protocols mpls
{% if mpls.traffic_engineering in [True, 'enabled'] %}
set groups {{ group_name }} protocols mpls traffic-engineering
{% endif %}
{% if mpls.rsvp %}
# ==================== RSVP CONFIGURATION ====================
set groups {{ group_name }} protocols rsvp
{% if mpls.rsvp.enabled %}
set groups {{ group_name }} protocols rsvp interface all
{% if mpls.rsvp.refresh_interval %}
set groups {{ group_name }} protocols rsvp refresh-interval {{ mpls.rsvp.refresh_interval }}
{% endif %}
{% if mpls.rsvp.fast_reroute in [True, 'enabled'] %}
set groups {{ group_name }} protocols rsvp graceful-restart enable
set groups {{ group_name }} protocols rsvp graceful-restart restart-time 120
{% endif %}
{% if mpls.rsvp.lsp_optimization in [True, 'enabled'] %}
set groups {{ group_name }} protocols rsvp optimize bandwidth
{% endif %}
{% endif %}
{% if mpls.rsvp.label_distribution %}
set groups {{ group_name }} protocols ldp interface all
{% endif %}
{% endif %}
{% endif %}
{% if lsp_templates %}
# ==================== LSP TEMPLATES ====================
{% for template_name, template_config in lsp_templates.items() %}
# Template: {{ template_name }}
# Description: {{ template_config.description | default('No description') }}
# Bandwidth: {{ template_config.bandwidth | default('Default') }}
# Priority: {{ template_config.priority | default('7 7') }}
{% endfor %}
{% endif %}
{% if lsp_groups %}
# ==================== LSP GROUPS ====================
# Total LSP Groups: {{ lsp_groups | length }}
{% for group in lsp_groups %}
# ───────────────────────────────────────────────────────────────
# LSP Group: {{ group.name }}
# ───────────────────────────────────────────────────────────────
# Range: {{ group.range[0] }}-{{ group.range[1] }} ({{ group.range[1] - group.range[0] + 1 }} LSPs)
# Destination: {{ group.destination }}
# Template: {{ group.template }}
{% if group.install_route %}
# Install Route: {{ group.install_route }}
{% endif %}
{% if group.install_route_base %}
# Install Route Mode: Sequential {{ group.install_route_mode | default('linear') }}
# Base: {{ group.install_route_base }}, Count: {{ group.install_route_count }}, Step: {{ group.install_route_step | default(1) }}
{% endif %}
{% set start = group.range[0] %}
{% set end = group.range[1] %}
{% set template = lsp_templates.get(group.template, {}) %}
{% for i in range(start, end + 1) %}
{% set lsp_name = group.name ~ '_' ~ i %}
set groups {{ group_name }} protocols mpls label-switched-path {{ lsp_name }} to {{ group.destination }}
{% if template.bandwidth %}
set groups {{ group_name }} protocols mpls label-switched-path {{ lsp_name }} bandwidth {{ template.bandwidth }}
{% endif %}
{% if template.priority %}
set groups {{ group_name }} protocols mpls label-switched-path {{ lsp_name }} priority {{ template.priority }}
{% endif %}
{% if template.adaptive in [True, 'enabled'] %}
set groups {{ group_name }} protocols mpls label-switched-path {{ lsp_name }} adaptive
{% endif %}
{% if template.fast_reroute in [True, 'enabled'] %}
set groups {{ group_name }} protocols mpls label-switched-path {{ lsp_name }} fast-reroute
{% endif %}
{% if template.description %}
set groups {{ group_name }} protocols mpls label-switched-path {{ lsp_name }} description "{{ template.description }}"
{% endif %}
{# Single static install_route #}
{% if group.install_route %}
set groups {{ group_name }} protocols mpls label-switched-path {{ lsp_name }} install destination-prefix {{ group.install_route }}
{% endif %}
{# Pre-expanded install_routes_list from Python (handles both small lists and generated large sequential ranges) #}
{% if group._expanded_install_routes is defined and group._expanded_install_routes is not none %}
{% set idx = i - start %}
{% if idx < group._expanded_install_routes | length %}
{% set assigned = group._expanded_install_routes[idx] %}
set groups {{ group_name }} protocols mpls label-switched-path {{ lsp_name }} install destination-prefix {{ assigned }}
{% endif %}
{% endif %}
{# IP pool for source address #}
{% if group.ip_pool_base and group.lsps_per_ip %}
{% set base_ip = group.ip_pool_base.split('/')[0] %}
{% set lsp_index = i - start %}
{% set pool_index = (lsp_index // group.lsps_per_ip) %}
{% set pool_increment = group.pool_increment | default(1) %}
{% set ip_increment = pool_index * pool_increment %}
{% set octets = base_ip.split('.') %}
{% set last_octet = (octets[3] | int) + ip_increment %}
{% set pool_ip = octets[0] ~ '.' ~ octets[1] ~ '.' ~ octets[2] ~ '.' ~ last_octet %}
set groups {{ group_name }} protocols mpls label-switched-path {{ lsp_name }} from {{ pool_ip }}
{% endif %}
{% endfor %}
{% endfor %}
{% endif %}
# ==================== END OF MPLS CONFIGURATION FOR {{ router_name }} ====================
"""

    def __init__(self, output_directory: str = "mpls_configs"):
        self.config: Dict[str, Any] = {}
        self.env = Environment()
        self.output_directory = output_directory

        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)
            print(f"✓ Created output directory: {self.output_directory}/")

    def load_yaml(self, path: str) -> None:
        """Load YAML configuration file"""
        try:
            with open(path, "r") as f:
                self.config = yaml.safe_load(f)
            print(f"✓ YAML file loaded: {path}\n")
        except FileNotFoundError:
            print(f"✗ Error: File '{path}' not found")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"✗ Error parsing YAML: {e}")
            sys.exit(1)

    @staticmethod
    def _extract_templates(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Extract template definitions (skip 'groups' key)"""
        if not raw:
            return {}
        return {k: v for k, v in raw.items() if k != "groups" and isinstance(v, dict)}

    @staticmethod
    def _get_group_name(router_cfg: Dict[str, Any]) -> str:
        """Get group name from router config (priority: mpls.groups > lsp_templates.groups > default)"""
        mpls = router_cfg.get("mpls", {})
        if isinstance(mpls, dict) and "groups" in mpls:
            return mpls.get("groups") or "_MPLS_CFG"
        lsp_t = router_cfg.get("lsp_templates", {})
        if isinstance(lsp_t, dict) and "groups" in lsp_t:
            return lsp_t.get("groups") or "_MPLS_CFG"
        return "_MPLS_CFG"

    @staticmethod
    def _build_sequential_routes(
        base: str, count: int, step: int, mode: str, total_lsps: int
    ) -> List[str]:
        """
        Build a list of prefixes for every LSP index.

        Args:
            base: e.g. '1.2.3.5/32'
            count: number of unique IPs to generate
            step: increment per IP (usually 1)
            mode: 'linear' (reuse last IP) or 'cyclic' (wrap around)
            total_lsps: number of LSPs in group

        Returns:
            List of prefixes, one per LSP
        """
        try:
            ip_str, prefix_len = base.split("/")
            base_ip = ipaddress.IPv4Address(ip_str)
            prefix_len = int(prefix_len)
        except (ValueError, AttributeError) as e:
            print(f"✗ Error parsing install_route_base '{base}': {e}")
            sys.exit(1)

        # Precompute IP pool
        pool = [
            f"{ipaddress.IPv4Address(int(base_ip) + i * step)}/{prefix_len}"
            for i in range(count)
        ]

        routes = []
        for idx in range(total_lsps):
            if mode == "linear":
                # After we run out of unique IPs, keep using the last one
                if idx < count:
                    routes.append(pool[idx])
                else:
                    routes.append(pool[-1])
            else:  # cyclic
                routes.append(pool[idx % count])
        return routes

    def _prepare_lsp_groups(self, router_cfg: Dict[str, Any]) -> List[Dict]:
        """
        Pre-process lsp_groups:
        - handle large sequential IPv4 install-route specs
        - expand small install_routes lists
        - attach _expanded_install_routes list when needed
        """
        groups = router_cfg.get("lsp_groups", [])
        for g in groups:
            rng = g.get("range", [0, 0])
            total_lsps = rng[1] - rng[0] + 1

            # NEW: Large-scale sequential IPv4 fields
            base = g.get("install_route_base")
            cnt = g.get("install_route_count")
            step = g.get("install_route_step", 1)
            mode = g.get("install_route_mode", "linear")  # 'linear' or 'cyclic'

            # DEBUG: Print what we're processing
            print(f"  Processing group: {g.get('name')}")
            print(f"    - base: {base}, count: {cnt}, step: {step}, mode: {mode}")

            if base and cnt:
                # Build sequential IPs
                expanded = self._build_sequential_routes(
                    base=base,
                    count=int(cnt),
                    step=int(step),
                    mode=str(mode),
                    total_lsps=total_lsps,
                )
                g["_expanded_install_routes"] = expanded
                print(
                    f"    ✓ Generated {len(expanded)} sequential install-route prefixes"
                )
                print(f"      First 3: {expanded[:3]}")
                print(f"      Last 3: {expanded[-3:]}")

            # LEGACY: Small manual list
            elif "install_routes" in g and isinstance(g["install_routes"], list):
                routes_list = g["install_routes"]
                n = len(routes_list)
                expanded = []
                for idx in range(total_lsps):
                    expanded.append(routes_list[idx % n])
                g["_expanded_install_routes"] = expanded
                print(
                    f"    ✓ Using {n} install-route(s) (cycling across {total_lsps} LSPs)"
                )
            else:
                print(f"    - No large-scale or small-list install routes")

        return groups

    def _generate_router_config(self, name: str, router_cfg: Dict[str, Any]) -> str:
        """Generate MPLS configuration for a single router"""
        group_name = self._get_group_name(router_cfg)
        lsp_templates_raw = router_cfg.get("lsp_templates", {})
        lsp_templates = self._extract_templates(lsp_templates_raw)
        lsp_groups = self._prepare_lsp_groups(router_cfg)

        ctx = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "router_name": name.upper(),
            "group_name": group_name,
            "mpls": router_cfg.get("mpls", {}),
            "lsp_templates": lsp_templates,
            "lsp_groups": lsp_groups,
        }

        tmpl = self.env.from_string(self.MASTER_MPLS_TEMPLATE)
        return tmpl.render(**ctx)

    def generate_all(self) -> None:
        """Generate config files for all routers"""
        routers = self.config.get("routers", {})
        if not routers:
            print("✗ No routers found in YAML.")
            return

        print(f"Processing {len(routers)} router(s)...\n")
        total_commands = 0

        for rname, rcfg in routers.items():
            print(f"[*] Router: {rname.upper()}")

            # Count LSPs
            lsp_groups = rcfg.get("lsp_groups", [])
            total_lsps = sum(
                g.get("range", [0, 0])[1] - g.get("range", [0, 0])[0] + 1
                for g in lsp_groups
            )
            print(f"    LSP Groups: {len(lsp_groups)} | Total LSPs: {total_lsps}")

            # Generate config
            text = self._generate_router_config(rname, rcfg)
            fname = f"{rname}_mpls.config"
            fpath = os.path.join(self.output_directory, fname)
            with open(fpath, "w") as f:
                f.write(text)

            # Count commands
            cmd_count = sum(1 for line in text.split("\n") if line.strip().startswith("set groups"))
            total_commands += cmd_count
            size_kb = len(text) / 1024

            print(f"    Output: {fpath}")
            print(f"    Commands: {cmd_count} | Size: {size_kb:.1f} KB\n")

        print("=" * 70)
        print(f"✓ Configuration generation complete!")
        print(f"  Files generated: {len(routers)}")
        print(f"  Total commands: {total_commands}")
        print(f"  Output directory: {self.output_directory}/")
        print("=" * 70)


def main():
    if len(sys.argv) < 2:
        print("\n" + "╔" + "═" * 68 + "╗")
        print("║ MPLS SCALE GENERATOR - Large-Scale IPv4 Support                ║")
        print("║ v2.3 - Sequential Install-Routes without listing thousands     ║")
        print("╚" + "═" * 68 + "╝\n")
        print("Usage: python mpls_scale_generator.py <input_yaml> [output_dir]\n")
        print("Arguments:")
        print("  <input_yaml>   : YAML configuration file")
        print("  [output_dir]   : Output directory (default: mpls_configs)\n")
        print("Examples:")
        print("  python mpls_scale_generator.py ultimate_multi_routers_1127.yaml")
        print("  python mpls_scale_generator.py config.yaml ./deployment/\n")
        sys.exit(1)

    yaml_file = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "mpls_configs"

    print("\n" + "╔" + "═" * 68 + "╗")
    print("║ MPLS SCALE GENERATOR - Large-Scale IPv4 Support                ║")
    print("║ v2.3 - Sequential Install-Routes without listing thousands     ║")
    print("╚" + "═" * 68 + "╝\n")

    gen = MPLSScaleGenerator(out_dir)
    gen.load_yaml(yaml_file)
    gen.generate_all()


if __name__ == "__main__":
    main()
