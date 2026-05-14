# Courier Management System

![Version](https://img.shields.io/badge/version-1.0-blue)
![Category](https://img.shields.io/badge/category-Uncategorized-green)
![License](https://img.shields.io/badge/license-LGPL-3-orange)
![Type](https://img.shields.io/badge/type-Application-purple)

| | |
|---|---|
| **Name** | Courier Management System |
| **Version** | 1.0 |
| **Category** | Uncategorized |
| **License** | LGPL-3 |
| **Application** | Yes |

## Description

Courier-style request -> internal request order flow with FinCodeMaster and transit hubs

## Functionality

### Models & Fields

#### Extends `account.move`

**File:** `models/account_move_inherit.py`

**Inherits:** `account.move`

**Fields:**

| Field | Type |
|-------|------|
| `payment_count` | `Integer` |
| `primary_payment_id` | `Many2one` |

**Key Methods:**

- `_get_request_from_invoice()`
- `action_post()` — Action/workflow method
- `_compute_linked_payments()` — Computed field
- `action_register_payment()` — Action/workflow method
- `action_open_payments()` — Action/workflow method

#### Extends `account.payment`

**File:** `models/account_payment_inherit.py`

**Inherits:** `account.payment`

**Fields:**

| Field | Type |
|-------|------|
| `codeware_request_id` | `Many2one` |

#### `codeware.request` — Request Form (Quotation-like)

**File:** `models/codeware_request.py`

**Inherits:** `res.partner`, `res.partner`, `mail.thread`, `mail.activity.mixin`, `mail.thread`, `mail.activity.mixin`

**Fields:**

| Field | Type |
|-------|------|
| `name` | `Char` |
| `partner_id` | `Many2one` |
| `source_hub_id` | `Many2one` |
| `sender_name` | `Char` |
| `sender_address` | `Text` |
| `sender_phone` | `Char` |
| `sender_phone_partner` | `Many2one` |
| `receiver_id` | `Many2one` |
| `customer_name` | `Char` |
| `customer_address` | `Text` |
| `receiver_phone` | `Char` |
| `receiver_phone_partner` | `Many2one` |
| `delivery_description` | `Char` |
| `priority_type` | `Selection` |
| `zip_input` | `Char` |
| `dest_fincode_id` | `Many2one` |
| `dest_zip` | `Char` |
| `city` | `Char` |
| `state_name` | `Char` |
| `base_price` | `Float` |
| `transit_hub_ids` | `Many2many` |
| `weight` | `Float` |
| `distance` | `Float` |
| `subtotal` | `Float` |
| `weight_cost` | `Float` |
| `distance_cost` | `Float` |
| `priority_cost` | `Float` |
| `line_ids` | `One2many` |
| `amount_total` | `Float` |
| `is_fully_paid` | `Boolean` |
| `state` | `Selection` |
| `request_order_id` | `Many2one` |
| `request_order_count` | `Integer` |
| `tracking_number` | `Char` |
| `serviced_by_id` | `Many2one` |
| `sale_id` | `Many2one` |
| `invoice_ids` | `Many2many` |
| `payment_ids` | `Many2many` |
| `primary_payment_id` | `Many2one` |
| `sale_count` | `Integer` |
| `payment_count` | `Integer` |
| `is_courier_hidden` | `Boolean` |
| `final_transit_hub` | `Many2one` |

**Key Methods:**

- `_get_partner_phone()`
- `_compute_priority_type_from_lines()` — Computed field
- `_onchange_line_ids_priority()` — Onchange handler
- `_compute_is_courier_hidden()` — Computed field
- `_compute_request_order_count()` — Computed field
- `_compute_link_counts()` — Computed field
- `_compute_tracking_number()` — Computed field
- `_onchange_zip_input()` — Onchange handler
- `_onchange_dest_fincode_id()` — Onchange handler
- `action_send_quotation()` — Action/workflow method
- `action_confirm()` — Action/workflow method
- `action_confirm()` — Action/workflow method
- `action_create_payment()` — Action/workflow method
- `action_view_request_order()` — Action/workflow method
- `action_print_request()` — Action/workflow method
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `action_open_sale_order()` — Action/workflow method
- `action_open_payments()` — Action/workflow method
- `_compute_is_fully_paid()` — Computed field
- `_onchange_partner_id()` — Onchange handler
- `_onchange_receiver_id()` — Onchange handler
- `_onchange_receiver_phone()` — Onchange handler
- `_onchange_sender_phone_partner()` — Onchange handler
- `_onchange_receiver_phone_partner()` — Onchange handler
- `_compute_amounts()` — Computed field
- `_compute_total()` — Computed field
- `_get_partner_phone()`
- `_compute_request_order_count()` — Computed field
- `_compute_link_counts()` — Computed field
- `_compute_tracking_number()` — Computed field
- `_onchange_zip_input()` — Onchange handler
- `_onchange_dest_fincode_id()` — Onchange handler
- `_onchange_dest_fincode_id()` — Onchange handler
- `action_send_quotation()` — Action/workflow method
- `action_confirm()` — Action/workflow method
- `action_confirm()` — Action/workflow method
- `_get_service_product()`
- `action_create_payment()` — Action/workflow method
- `action_view_request_order()` — Action/workflow method
- `action_print_request()` — Action/workflow method
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `action_open_sale_order()` — Action/workflow method
- `action_open_payments()` — Action/workflow method
- `_compute_is_fully_paid()` — Computed field
- `_onchange_partner_id()` — Onchange handler
- `_onchange_receiver_id()` — Onchange handler
- `_onchange_receiver_phone()` — Onchange handler
- `_onchange_sender_phone_partner()` — Onchange handler
- `_onchange_receiver_phone_partner()` — Onchange handler
- `_compute_amounts()` — Computed field
- `_compute_total()` — Computed field

#### `codeware.courier.company` — Third-party Courier Company / Service Provider

**File:** `models/courier_company.py`

**Inherits:** `mail.thread`, `mail.activity.mixin`, `mail.thread`, `mail.activity.mixin`

**Fields:**

| Field | Type |
|-------|------|
| `name` | `Char` |
| `partner_id` | `Many2one` |
| `contact_person` | `Char` |
| `phone` | `Char` |
| `email` | `Char` |
| `address` | `Text` |
| `notes` | `Text` |
| `active` | `Boolean` |
| `internal` | `Boolean` |
| `courier_product_id` | `Many2one` |

**Key Methods:**

- `_onchange_partner_id_fill_fields()` — Onchange handler
- `_onchange_partner_id_fill_fields()` — Onchange handler

#### `codeware.fincode` — FinCode Master - ZIP / Area master with hubs

**File:** `models/fincode_master.py`

**Fields:**

| Field | Type |
|-------|------|
| `name` | `Char` |
| `city` | `Char` |
| `state` | `Char` |
| `base_price` | `Float` |
| `serviced_by_id` | `Many2one` |
| `hub_ids` | `Many2many` |
| `hub_pincodes` | `Char` |
| `cod_available` | `Boolean` |
| `is_internal_courier` | `Boolean` |
| `final_transit_hub_id` | `Many2one` |

**Key Methods:**

- `_compute_final_transit_hub()` — Computed field
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method

#### `handoff.wizard` — Wizard to Create Handoff (mirror courier.handoff fields)

**File:** `models/handoff_wizard.py`

**Fields:**

| Field | Type |
|-------|------|
| `picking_id` | `Many2many` |
| `picking_type_id` | `Many2one` |
| `company_location_id` | `Many2one` |
| `name` | `Char` |
| `vehicle_number` | `Char` |
| `driver_id` | `Many2one` |
| `vehicle_id` | `Many2one` |
| `courier_partner_id` | `Many2one` |
| `manifest_ref` | `Char` |
| `notes` | `Text` |
| `parcel_count` | `Integer` |
| `assigned_datetime` | `Datetime` |
| `picked_datetime` | `Datetime` |
| `delivered_datetime` | `Datetime` |
| `state` | `Selection` |
| `created_by` | `Many2one` |
| `sale_id` | `Many2one` |
| `awb_number` | `Char` |
| `authorized_person` | `Char` |
| `serviced_by_id` | `Many2one` |
| `internal` | `Boolean` |

**Key Methods:**

- `_compute_company_location()` — Computed field
- `_onchange_vehicle_id()` — Onchange handler
- `_onchange_picking_id()` — Onchange handler
- `_onchange_vehicle_number()` — Onchange handler
- `action_confirm_handoff()` — Action/workflow method
- `action_confirm_handoff()` — Action/workflow method

#### `courier.handoff` — Courier Handoff / Delivery Handoff

**File:** `models/handoffs.py`

**Inherits:** `stock.picking`, `stock.picking`, `sale.order`

**Fields:**

| Field | Type |
|-------|------|
| `name` | `Char` |
| `picking_id` | `Many2one` |
| `vehicle_number` | `Char` |
| `sale_id` | `Many2one` |
| `partner_id` | `Many2one` |
| `vehicle_id` | `Many2one` |
| `driver_id` | `Many2one` |
| `courier_partner_id` | `Many2one` |
| `assigned_datetime` | `Datetime` |
| `picked_datetime` | `Datetime` |
| `delivered_datetime` | `Datetime` |
| `state` | `Selection` |
| `parcel_count` | `Integer` |
| `total_weight` | `Float` |
| `manifest_ref` | `Char` |
| `notes` | `Text` |
| `gps_lat` | `Float` |
| `gps_lon` | `Float` |
| `created_by` | `Many2one` |
| `awb_number` | `Char` |
| `authorized_person` | `Char` |
| `serviced_by_id` | `Many2one` |
| `internal` | `Boolean` |
| `handoff_ids` | `One2many` |
| `handoff_count` | `Integer` |
| `primary_handoff_id` | `Many2one` |

**Key Methods:**

- `create()` — Overridden ORM method
- `create()` — Overridden ORM method
- `_compute_sale_id()` — Computed field
- `_onchange_vehicle_id()` — Onchange handler
- `action_mark_assigned()` — Action/workflow method
- `action_mark_picked()` — Action/workflow method
- `action_mark_delivered()` — Action/workflow method
- `action_cancel()` — Action/workflow method
- `action_print_handoff()` — Action/workflow method
- `_compute_handoff_count()` — Computed field
- `_compute_primary_handoff()` — Computed field
- `action_create_handoff()` — Action/workflow method
- `action_done()` — Action/workflow method
- `button_validate()` — Button handler
- `_compute_handoff_count()` — Computed field
- `_compute_primary_handoff()` — Computed field
- `action_open_handoffs()` — Action/workflow method
- `action_open_handoffs_multi()` — Action/workflow method
- `action_open_handoffs()` — Action/workflow method
- `action_open_handoffs_multi()` — Action/workflow method
- `action_open_handoffs()` — Action/workflow method

#### Extends `res.partner`

**File:** `models/partner_inherit.py`

**Inherits:** `res.partner`

**Fields:**

| Field | Type |
|-------|------|
| `is_transit_hub` | `Boolean` |
| `portal_location_id` | `Many2one` |
| `vendor_ack_count` | `Integer` |

#### `codeware.pricing.rule` — Pricing Rule

**File:** `models/pricing_rule.py`

**Fields:**

| Field | Type |
|-------|------|
| `name` | `Char` |
| `priority_type` | `Selection` |
| `min_weight` | `Float` |
| `max_weight` | `Float` |
| `price_per_kg` | `Float` |
| `discount_percent` | `Float` |
| `active` | `Boolean` |
| `rules` | `Text` |
| `priority` | `Selection` |
| `cost` | `Float` |
| `status` | `Selection` |
| `min_distance` | `Float` |
| `max_distance` | `Float` |

#### Extends `purchase.order, purchase.order.line, purchase.order, purchase.order.line`

**File:** `models/purchase_order_inherit.py`

**Inherits:** `purchase.order`, `purchase.order.line`, `purchase.order`, `purchase.order.line`

**Fields:**

| Field | Type |
|-------|------|
| `awb_number` | `Char` |
| `barcode_number` | `Char` |
| `sale_order_count` | `Integer` |
| `sale_order_ids` | `Many2many` |
| `has_sale_order` | `Boolean` |

**Key Methods:**

- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `action_merge()` — Action/workflow method
- `_compute_sale_order_info()` — Computed field
- `action_view_sale_orders()` — Action/workflow method

#### `codeware.request.line` — Request - Price Line

**File:** `models/request_line.py`

**Fields:**

| Field | Type |
|-------|------|
| `request_id` | `Many2one` |
| `product_desc` | `Char` |
| `product_id` | `Many2one` |
| `weight` | `Float` |
| `distance_km` | `Float` |
| `priority` | `Selection` |
| `price_rule_id` | `Many2one` |
| `unit_price` | `Float` |
| `price_subtotal` | `Float` |
| `is_cod` | `Boolean` |
| `cod_amount` | `Float` |
| `weight_cost` | `Float` |
| `distance_cost` | `Float` |
| `priority_cost` | `Float` |
| `courier_company_id` | `Many2one` |
| `is_courier_hidden` | `Boolean` |

**Key Methods:**

- `_compute_is_courier_hidden()` — Computed field
- `_compute_subtotal()` — Computed field
- `_onchange_is_cod()` — Onchange handler
- `_compute_amounts()` — Computed field

#### `codeware.request.order` — Internal Request Order

**File:** `models/request_order.py`

**Inherits:** `mail.thread`, `mail.activity.mixin`, `mail.thread`, `mail.activity.mixin`

**Fields:**

| Field | Type |
|-------|------|
| `name` | `Char` |
| `request_id` | `Many2one` |
| `partner_id` | `Many2one` |
| `source_hub_id` | `Many2one` |
| `dest_zip` | `Char` |
| `city` | `Char` |
| `state_name` | `Char` |
| `total_amount` | `Float` |
| `sender_name` | `Char` |
| `sender_address` | `Text` |
| `customer_name` | `Char` |
| `customer_address` | `Text` |
| `state` | `Selection` |
| `tracking_number` | `Char` |
| `barcode_image` | `Binary` |

**Key Methods:**

- `action_print_pdf()` — Action/workflow method
- `action_print_pdf()` — Action/workflow method

#### Extends `sale.order, sale.order.line, sale.order, sale.order.line`

**File:** `models/sale_integration.py`

**Inherits:** `sale.order`, `sale.order.line`, `sale.order`, `sale.order.line`

**Fields:**

| Field | Type |
|-------|------|
| `request_id` | `Many2one` |
| `x_barcode` | `Char` |
| `delivery_hub_id` | `Many2one` |
| `fincode_id` | `Many2one` |
| `awb_number` | `Char` |
| `barcode_number` | `Char` |
| `hide_ecommerce_info` | `Boolean` |
| `request_line_id` | `Many2one` |
| `is_courier_hidden` | `Boolean` |
| `request_subtotal` | `Float` |

**Key Methods:**

- `_compute_hide_ecommerce_info()` — Computed field
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `_compute_is_courier_hidden()` — Computed field
- `_compute_price_unit()` — Computed field

#### Extends `sale.order, sale.order, sale.order, sale.order, sale.order`

**File:** `models/sale_order_inherit.py`

**Inherits:** `sale.order`, `sale.order`, `sale.order`, `sale.order`, `sale.order`

**Fields:**

| Field | Type |
|-------|------|
| `serviced_by_id` | `Many2one` |
| `purchase_order_count` | `Integer` |
| `purchase_order_ids` | `Many2many` |

**Key Methods:**

- `_onchange_serviced_by_id()` — Onchange handler
- `_compute_purchase_orders()` — Computed field
- `action_view_purchase_orders()` — Action/workflow method
- `_compute_purchase_orders()` — Computed field
- `action_view_purchase_orders()` — Action/workflow method
- `_compute_purchase_orders()` — Computed field
- `action_view_purchase_orders()` — Action/workflow method
- `_compute_purchase_orders()` — Computed field
- `action_view_purchase_orders()` — Action/workflow method
- `action_view_purchase_orders()` — Action/workflow method

#### Extends `stock.picking`

**File:** `models/stock_picking.py`

**Inherits:** `stock.picking`

**Fields:**

| Field | Type |
|-------|------|
| `picking_serviced_by_id` | `Many2one` |

#### Extends `stock.picking, stock.move`

**File:** `models/stock_picking_inherit.py`

**Inherits:** `stock.picking`, `stock.move`

**Fields:**

| Field | Type |
|-------|------|
| `receiver_name` | `Char` |
| `receiver_phone` | `Char` |
| `receiver_address` | `Text` |
| `receiver_zip` | `Char` |
| `picking_serviced_by_id` | `Char` |
| `awb_number` | `Char` |
| `barcode_number` | `Char` |
| `priority_type` | `Selection` |
| `delivery_description` | `Char` |
| `handoff_ref` | `Char` |
| `is_courier_hidden` | `Boolean` |

**Key Methods:**

- `button_validate()` — Button handler
- `_compute_is_courier_hidden()` — Computed field

#### Extends `res.partner, stock.picking`

**File:** `models/stock_picking_integration.py`

**Inherits:** `res.partner`, `stock.picking`

**Fields:**

| Field | Type |
|-------|------|
| `transit_location_id` | `Many2one` |
| `planned_location_ids` | `Many2many` |
| `courier_request_id` | `Many2one` |

**Key Methods:**

- `create()` — Overridden ORM method
- `button_validate()` — Button handler

#### Extends `stock.lot`

**File:** `models/stocklot.py`

**Inherits:** `stock.lot`

**Fields:**

| Field | Type |
|-------|------|
| `awb_number` | `Char` |
| `delivery_order` | `Char` |
| `barcode_number` | `Char` |
| `picking_id` | `Many2one` |

#### `codeware.transithub` — Transit Hub

**File:** `models/transit_hub.py`

**Fields:**

| Field | Type |
|-------|------|
| `name` | `Char` |
| `hub_code` | `Char` |
| `sequence` | `Integer` |
| `location` | `Char` |
| `stock_location_id` | `Many2one` |
| `pincode` | `Char` |

### Views & UI

**Form Views:** `codeware_menus_views.xml`, `handoff_wizard.xml`, `handoffsviews.xml`

**List/Tree Views:** `codeware_menus_views.xml`, `handoffsviews.xml`, `sale_order_line_hide.xml`

**Menus:** `codeware_menus_views.xml`, `handoffsviews.xml`

**Website/Portal Templates:**

- `web.assets_backend` (`assets.xml`)
- `report_request_order` (`report_request_order.xml`)
- `report_request_order` (`report_request_order.xml`)
- `report_request_order_v2` (`report_request_order_v2.xml`)

### Security

**Access Rights:** 12 model access rules defined

| Model |
|-------|
| `access_codeware_fincode_user` |
| `access_codeware_transithub_user` |
| `access_codeware_pricingrule_user` |
| `access_codeware_requestline_user` |
| `access_codeware_request_user` |
| `access_codeware_request_order_user` |
| `access_codeware_priority_pricelist` |
| `access_codeware_distance_pricelist` |
| `access_codeware_weight_pricelist` |
| `courier.handoff` |
| `handoff.wizard` |
| `access.courier.company` |

### Reports

- `report_courier_handoff.xml`
- `report_courier_handoff_template.xml`
- `report_handoff_wizard.xml`
- `report_handoff_wizard_template.xml`

## Dependencies

| Module | Type |
|--------|------|
| `sale` | Odoo Core |
| `stock` | Odoo Core |
| `account` | Odoo Core |
| `mail` | Odoo Core |
| `sale_management` | Odoo Core |
| `purchase` | Odoo Core |
| `fleet` | Odoo Core |
| `portal` | Odoo Core |
| `vendor_dispatch_portal_v2` | Custom |

## File Structure

```
courier_management_final/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── account_move_inherit.py
│   ├── account_payment_inherit.py
│   ├── codeware_request.py
│   ├── courier_company.py
│   ├── fincode_master.py
│   ├── handoff_wizard.py
│   ├── handoffs.py
│   ├── partner_inherit.py
│   ├── post_init.py
│   ├── pricing_rule.py
│   ├── purchase_order_inherit.py
│   ├── request_line.py
│   ├── request_order.py
│   ├── sale_integration.py
│   ├── sale_order_inherit.py
│   ├── stock_picking.py
│   ├── stock_picking_inherit.py
│   ├── stock_picking_integration.py
│   ├── stocklot.py
│   └── transit_hub.py
├── report/
│   ├── report_courier_handoff.xml
│   ├── report_courier_handoff_template.xml
│   ├── report_handoff_wizard.xml
│   └── report_handoff_wizard_template.xml
├── security/
│   └── ir.model.access.csv
└── views/
    ├── account_move_inherit_views.xml
    ├── account_payment_views.xml
    ├── assets.xml
    ├── codeware_menus_views.xml
    ├── data_sequences.xml
    ├── handoff_wizard.xml
    ├── handoffsviews.xml
    ├── partner_views.xml
    ├── purchase_order_awb_view.xml
    ├── report_request_order.xml
    ├── report_request_order_v2.xml
    ├── sale_order_awb_view.xml
    ├── sale_order_line_hide.xml
    ├── stock_picking_inherit_views.xml
    └── stocklotviews.xml
```

## Installation

This module is part of the **[odoo-logistics-courier-suite](https://github.com/tejas7287/odoo-logistics-courier-suite)** suite.

1. Place this module in your Odoo addons directory
2. Update the apps list: **Settings** → **Apps** → **Update Apps List**
3. Search for **"Courier Management System"** and click **Install**

## License

LGPL-3
