# Vendor Dispatch Portal

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Category](https://img.shields.io/badge/category-Warehouse-green)
![License](https://img.shields.io/badge/license-LGPL-3-orange)

| | |
|---|---|
| **Name** | Vendor Dispatch Portal |
| **Version** | 1.0.0 |
| **Category** | Warehouse |
| **Author** | Prime Minds Services for User |
| **License** | LGPL-3 |
| **Application** | No (Addon) |

## Description

Vendor portal to submit dispatch details for dropship orders; customers can view them.

## Functionality

### Models & Fields

#### Extends `res.partner, stock.picking, res.partner, stock.picking`

**File:** `models/dispatch_models.py`

**Inherits:** `res.partner`, `stock.picking`, `res.partner`, `stock.picking`

**Fields:**

| Field | Type |
|-------|------|
| `vendor_portal` | `Boolean` |
| `vendor_dispatch_reference` | `Char` |
| `vendor_dispatch_date` | `Date` |
| `vendor_dispatch_location_id` | `Many2one` |
| `vendor_dispatch_location` | `Char` |
| `vendor_expected_delivery_date` | `Date` |
| `vendor_carrier_id` | `Many2one` |
| `vendor_carrier_name` | `Char` |
| `vendor_tracking_number` | `Char` |
| `vendor_notes` | `Text` |
| `vendor_invoice_number` | `Char` |
| `vendor_payment_status` | `Selection` |
| `vendor_delivery_status` | `Selection` |
| `vendor_purchase_order_id` | `Many2one` |
| `vendor_sale_order_id` | `Many2one` |

**Key Methods:**

- `_compute_vendor_sale_order()` — Computed field
- `_compute_vendor_purchase_order()` — Computed field

#### Extends `product.template, stock.rule, stock.quant, product.template, stock.rule, stock.quant, product.template`

**File:** `models/product_template.py`

**Inherits:** `product.template`, `stock.rule`, `stock.quant`, `product.template`, `stock.rule`, `stock.quant`, `product.template`

**Fields:**

| Field | Type |
|-------|------|
| `enable_dropship` | `Boolean` |

**Key Methods:**

- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `_get_rule()`
- `write()` — Overridden ORM method
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `_get_rule()`
- `write()` — Overridden ORM method
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method

#### Extends `product.template, stock.rule, stock.quant, product.template, stock.rule, stock.quant, product.template`

**File:** `models/product_template_bak.py`

**Inherits:** `product.template`, `stock.rule`, `stock.quant`, `product.template`, `stock.rule`, `stock.quant`, `product.template`

**Fields:**

| Field | Type |
|-------|------|
| `enable_dropship` | `Boolean` |

**Key Methods:**

- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `_get_rule()`
- `write()` — Overridden ORM method
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method
- `_get_rule()`
- `write()` — Overridden ORM method
- `create()` — Overridden ORM method
- `write()` — Overridden ORM method

#### Extends `stock.picking, stock.move`

**File:** `models/stock_picking.py`

**Inherits:** `stock.picking`, `stock.move`

**Fields:**

| Field | Type |
|-------|------|
| `vendor_portal_state` | `Selection` |
| `portal_acknowledged` | `Boolean` |
| `customer_tracking_status` | `Char` |
| `customer_last_location` | `Char` |
| `customer_sale_order` | `Char` |
| `customer_ordered_on` | `Datetime` |
| `customer_expected_on` | `Date` |
| `delivery_acknowledged` | `Boolean` |

**Key Methods:**

- `button_validate()` — Button handler
- `_compute_customer_tracking()` — Computed field
- `_compute_customer_tracking()` — Computed field
- `write()` — Overridden ORM method
- `_compute_is_quantity_done_editable()` — Computed field

#### Extends `stock.picking, stock.move, stock.picking`

**File:** `models/stock_picking1.py`

**Inherits:** `stock.picking`, `stock.move`, `stock.picking`

**Fields:**

| Field | Type |
|-------|------|
| `vendor_portal_state` | `Selection` |
| `portal_acknowledged` | `Boolean` |
| `customer_tracking_status` | `Char` |
| `customer_last_location` | `Char` |
| `customer_sale_order` | `Char` |

**Key Methods:**

- `_compute_customer_tracking()` — Computed field
- `button_validate()` — Button handler
- `_compute_is_quantity_done_editable()` — Computed field
- `button_validate()` — Button handler

### Views & UI

**Form Views:** `dispatch_templates.xml`, `dispatch_templatesmain.xml`

**Website/Portal Templates:**

- `portal.portal_my_home` (`dispatch_templates.xml`)
- `portal_vendor_dispatch_list` (`dispatch_templates.xml`)
- `portal.portal_sidebar` (`dispatch_templates.xml`)
- `portal.portal_my_home` (`dispatch_templates.xml`)
- `portal_vendor_acknowledgement_form` (`dispatch_templates.xml`)
- `portal_vendor_acknowledgement_list` (`dispatch_templates.xml`)
- `portal.portal_my_home` (`dispatch_templates.xml`)
- `portal.portal_my_home` (`dispatch_templates.xml`)
- `portal_customer_tracking_list` (`dispatch_templates.xml`)
- `portal_customer_tracking_form` (`dispatch_templates.xml`)
- `portal.portal_my_home` (`dispatch_templates.xml`)
- `portal.portal_my_home` (`dispatch_templates.xml`)
- `portal_stock_card_page` (`dispatch_templates.xml`)
- `portal.portal_my_home` (`dispatch_templatesmain.xml`)
- `portal_vendor_dispatch_list` (`dispatch_templatesmain.xml`)
- ... and 13 more

### Security

**Security Groups:**

- Vendor Portal User

**Access Rights:** 2 model access rules defined

| Model |
|-------|
| `access_vendor_dispatch_portal` |
| `access_vendor_dispatch_portal_admin` |

**Record Rules:** `security_rules.xml`

### Web Controllers & Routes

| Route | Controller |
|-------|------------|
| `/my/vendor_orders` | `dispatch_portal.py` |
| `/my/vendor_dispatch/<int:picking_id>` | `dispatch_portal.py` |
| `/my/vendor_orders/submit/<int:picking_id>` | `dispatch_portal.py` |
| `/my/vendor_acknowledgements` | `vendoracknowledgeportal.py` |
| `/my/vendor_acknowledgements/process` | `vendoracknowledgeportal.py` |
| `/my/vendor_acknowledgements/delete` | `vendoracknowledgeportal.py` |
| `/my/vendor_acknowledgements/<int:picking_id>` | `vendoracknowledgeportal.py` |
| `/my/vendor_acknowledgements/ack/<int:picking_id>` | `vendoracknowledgeportal.py` |
| `/my/stock/cards` | `vendoracknowledgeportal.py` |
| `/my/trackings` | `vendoracknowledgeportal.py` |
| `/my/trackings/page/<int:page>` | `vendoracknowledgeportal.py` |
| `/my/trackings/<int:picking_id>` | `vendoracknowledgeportal.py` |
| `/my/stock/cards` | `vendoracknowledgeportal.py` |
| `/my/vendor_acknowledgements` | `vendoracknowledgeportalmain.py` |
| `/my/vendor_acknowledgements/process` | `vendoracknowledgeportalmain.py` |
| `/my/vendor_acknowledgements/delete` | `vendoracknowledgeportalmain.py` |
| `/my/vendor_acknowledgements/<int:picking_id>` | `vendoracknowledgeportalmain.py` |
| `/my/vendor_acknowledgements/ack/<int:picking_id>` | `vendoracknowledgeportalmain.py` |
| `/my/trackings` | `vendoracknowledgeportalmain.py` |
| `/my/trackings/<int:picking_id>` | `vendoracknowledgeportalmain.py` |

### Frontend Assets

**CSS:**

- `static/src/css/customer_tracking.css`

## Dependencies

| Module | Type |
|--------|------|
| `base` | Odoo Core |
| `portal` | Odoo Core |
| `contacts` | Odoo Core |
| `stock` | Odoo Core |
| `delivery` | Odoo Core |
| `sale_management` | Odoo Core |
| `website` | Odoo Core |
| `stock_dropshipping` | Odoo Core |
| `sale` | Odoo Core |

## File Structure

```
vendor_dispatch_portal_v2/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── dispatch_portal.py
│   ├── vendoracknowledgeportal.py
│   └── vendoracknowledgeportalmain.py
├── models/
│   ├── __init__.py
│   ├── dispatch_models.py
│   ├── product_template.py
│   ├── product_template_bak.py
│   ├── stock_picking.py
│   └── stock_picking1.py
├── security/
│   ├── ir.model.access.csv
│   └── security_rules.xml
├── static/
│   └── src/
│       ├── Delivery_icon.svg
│       ├── bag.svg
│       ├── css/
│       ├── icon.svg
│       ├── operations.svg
│       ├── receipts.svg
│       └── stck_avail.svg
└── views/
    ├── dispatch_templates.xml
    ├── dispatch_templatesmain.xml
    ├── dispatch_views.xml
    ├── email_templates.xml
    └── product_template_view.xml
```

## Installation

This module is part of the **[odoo-logistics-courier-suite](https://github.com/tejas7287/odoo-logistics-courier-suite)** suite.

1. Place this module in your Odoo addons directory
2. Update the apps list: **Settings** → **Apps** → **Update Apps List**
3. Search for **"Vendor Dispatch Portal"** and click **Install**

## License

LGPL-3
