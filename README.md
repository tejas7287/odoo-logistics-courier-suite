# Odoo Logistics & Courier Management Suite

Complete courier and logistics management for Odoo — from vendor dispatch portals through multi-hop transit hub routing with automatic delivery chain creation.

## Workflow & Dependency Diagram

```
┌──────────────────────────────┐
│   vendor_dispatch_portal_v2  │
│   (Vendor Dispatch Portal)   │
│   Submit dispatch details    │
│   for dropship orders        │
└──────────────┬───────────────┘
               │ depends
               ▼
┌──────────────────────────────┐
│  courier_management_final    │
│  (Courier Management System) │
│                              │
│  Request → Sale Order →      │
│  Multi-hop Transit Routing:  │
│                              │
│  Warehouse → Hub A → Hub B   │
│  → Hub C → Customer          │
│                              │
│  Each hop = real stock.picking│
│  Auto-created on validation  │
└──────────────────────────────┘
```

## Modules Included

| # | Module | Name | Description |
|---|--------|------|-------------|
| 1 | `vendor_dispatch_portal_v2/` | Vendor Dispatch Portal | Website portal for vendors to submit dispatch details for dropship orders; customers can track them. |
| 2 | `courier_management_final/` | Courier Management System | Full courier request → internal order flow with FinCodeMaster, transit hubs, and staged hop delivery. |

## Installation Order

1. `vendor_dispatch_portal_v2` — Foundation (Dispatch Portal)
2. `courier_management_final` — Depends on `vendor_dispatch_portal_v2`

## Key Features

- **Transit Hub Routing**: Destination ZIP → automatic multi-hop route via transit hubs
- **Staged Hop Creation**: Each delivery validation auto-creates the next hop
- **AWB & Barcode Tracking**: Air Waybill and barcode generation during validation
- **Vendor Portal**: Vendors submit dispatch details with tracking
- **Customer Tracking**: Customers can view dispatch status via portal

## Setup

```bash
git clone https://github.com/tejas7287/odoo-logistics-courier-suite.git

# Add to odoo.conf
addons_path = /path/to/odoo/addons,/path/to/odoo-logistics-courier-suite
```

## License

LGPL-3 — See individual module manifests for specific licensing.
