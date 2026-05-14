# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ---------------------------------------------------------
    # FIELDS
    # ---------------------------------------------------------
    serviced_by_id = fields.Many2one(
        'codeware.courier.company',
        string="Serviced By"
    )

    purchase_order_count = fields.Integer(
        string="Purchase Orders",
        compute="_compute_purchase_orders",
        store=False
    )
    purchase_order_ids = fields.Many2many(
        "purchase.order",
        string="Purchase Orders",
        compute="_compute_purchase_orders"
    )

    # ---------------------------------------------------------
    # ONCHANGE: SERVICED BY → ADD / REPLACE COURIER LINE
    # ---------------------------------------------------------
    @api.onchange('serviced_by_id')
    def _onchange_serviced_by_id(self):
        if not self.serviced_by_id:
            return

        courier_product = self.serviced_by_id.courier_product_id
        if not courier_product:
            return

        # remove existing courier product lines
        courier_products = self.env['codeware.courier.company'].search([]).mapped('courier_product_id')
        self.order_line = self.order_line.filtered(
            lambda l: not l.product_id or l.product_id not in courier_products
        )

        # add new courier product line
        self.order_line += self.env['sale.order.line'].new({
            'order_id': self.id,
            'product_id': courier_product.id,
            'product_uom_qty': 1,
            'price_unit': courier_product.lst_price or 0.0,
            'name': courier_product.display_name,
        })

    # ---------------------------------------------------------
    # CONFIRM SALE ORDER
    # ---------------------------------------------------------
    def _action_confirm(self):
        res = super()._action_confirm()

        # create POs for NON-courier service products
        for order in self:
            try:
                order._create_po_for_non_courier_products()
            except Exception:
                _logger.exception(
                    "Error while creating purchase orders for non-courier products for sale %s",
                    order.name
                )

        # copy serviced_by into pickings
        for order in self:
            if order.serviced_by_id:
                for picking in order.picking_ids:
                    try:
                        picking.sudo().write({
                            'picking_serviced_by_id': order.serviced_by_id.id
                        })
                    except Exception:
                        _logger.exception(
                            "Failed to write serviced_by on picking %s (sale %s)",
                            picking.name, order.name
                        )

        return res

    # ---------------------------------------------------------
    # PO CREATION (NON-COURIER SERVICE PRODUCTS ONLY)
    # ---------------------------------------------------------
    def _create_po_for_non_courier_products(self):
        PurchaseOrder = self.env["purchase.order"]
        PurchaseOrderLine = self.env["purchase.order.line"]
        CourierCompany = self.env["codeware.courier.company"]

        courier_variant_ids = set()
        courier_template_ids = set()

        for c in CourierCompany.search([]):
            prod = c.courier_product_id
            if not prod:
                continue
            courier_variant_ids.add(prod.id)
            if prod.product_tmpl_id:
                courier_template_ids.add(prod.product_tmpl_id.id)

        for order in self:
            sale_lines = order.order_line.filtered(
                lambda l: l.product_id
                and not l.display_type
                and l.product_id.type == "service"
                and l.product_id.id not in courier_variant_ids
                and l.product_id.product_tmpl_id.id not in courier_template_ids
            )

            vendor_map = {}
            for line in sale_lines:
                product = line.product_id
                seller = product.seller_ids[:1] or product.product_tmpl_id.seller_ids[:1]
                if not seller:
                    continue
                seller = seller[0]
                vendor = seller.name or seller.partner_id
                if not vendor:
                    continue
                vendor_map.setdefault(vendor.id, []).append(line)

            for vendor_id, lines in vendor_map.items():
                po = PurchaseOrder.search(
                    [('origin', '=', order.name), ('partner_id', '=', vendor_id)],
                    limit=1
                )
                if not po:
                    po = PurchaseOrder.create({
                        'partner_id': vendor_id,
                        'origin': order.name,
                        'date_order': fields.Datetime.now(),
                        'company_id': order.company_id.id,
                    })

                for l in lines:
                    PurchaseOrderLine.create({
                        'order_id': po.id,
                        'product_id': l.product_id.id,
                        'name': l.product_id.display_name,
                        'product_qty': l.product_uom_qty,
                        'product_uom_id': l.product_uom_id.id,
                        'price_unit': l.product_id.standard_price or 0.0,
                        'date_planned': fields.Datetime.now() + timedelta(days=1),
                    })

        return True

    # ---------------------------------------------------------
    # PURCHASE ORDER COMPUTE / ACTION
    # ---------------------------------------------------------
    @api.depends("name")
    def _compute_purchase_orders(self):
        Purchase = self.env["purchase.order"]
        for order in self:
            if not order.name:
                order.purchase_order_ids = [(6, 0, [])]
                order.purchase_order_count = 0
                continue
            pos = Purchase.search([("origin", "=", order.name)])
            order.purchase_order_ids = [(6, 0, pos.ids)]
            order.purchase_order_count = len(pos)

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            "name": "Purchase Orders",
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("origin", "=", self.name)],
            "context": {"default_origin": self.name},
            "target": "current",
        }












































# -*- coding: utf-8 -*-
# import logging
# from datetime import timedelta
#
# from odoo import models, fields, api
#
# _logger = logging.getLogger(__name__)
#
#
# class SaleOrder(models.Model):
#     _inherit = "sale.order"
#
#     purchase_order_count = fields.Integer(
#         string="Purchase Orders", compute="_compute_purchase_orders", store=False
#     )
#     purchase_order_ids = fields.Many2many(
#         "purchase.order", string="Purchase Orders", compute="_compute_purchase_orders"
#     )
#
#
#     # def _action_confirm(self):
#     #     """
#     #     Call super confirm, then create POs for NON-courier products only,
#     #     and copy request -> picking data (if present).
#     #     """
#     #     # 1) call super to perform standard confirm operations (creates pickings, etc.)
#     #     res = super()._action_confirm()
#     #
#     #     # 2) create POs for NON-courier products (includes service products)
#     #     for order in self:
#     #         try:
#     #             order._create_po_for_non_courier_products()
#     #         except Exception:
#     #             _logger.exception("Error while creating purchase orders for non-courier products for sale %s", order.name)
#     #
#     #     # 3) copy request data into pickings created for the sale
#     #     for order in self:
#     #         # find request either via m2o or by matching origin
#     #         req = order.request_id
#     #         if not req and order.origin:
#     #             try:
#     #                 req = self.env['codeware.request'].search([('name', '=', order.origin)], limit=1)
#     #             except Exception:
#     #                 _logger.exception("Error searching codeware.request for origin %s", order.origin)
#     #                 req = None
#     #
#     #         if not req:
#     #             # nothing to copy for this order
#     #             continue
#     #
#     #         # find pickings created for this sale by origin (safe)
#     #         pickings = self.env['stock.picking'].search([('origin', '=', order.name)])
#     #         if not pickings:
#     #             # fallback to order.picking_ids (in case origin differs)
#     #             pickings = order.picking_ids
#     #
#     #         if not pickings:
#     #             continue
#     #
#     #         # prepare values to write (do not overwrite if empty)
#     #         vals = {
#     #             'receiver_name': req.customer_name or False,
#     #             'receiver_phone': req.receiver_phone_partner or req.receiver_phone or False,
#     #             'receiver_address': req.customer_address or False,
#     #             'receiver_zip': req.dest_zip or False,
#     #             'picking_serviced_by_id': req.serviced_by_id.id if req.serviced_by_id else False,
#     #         }
#     #
#     #         for picking in pickings:
#     #             try:
#     #                 # use sudo to avoid access right issues
#     #                 picking.sudo().write(vals)
#     #             except Exception:
#     #                 _logger.exception("Failed to write request->picking values for picking %s (sale %s)", picking.id,
#     #                                   order.name)
#     #
#     #     # 4) return the original result
#     #     return res
#     #
#     #
#     #
#     #
#     # def _create_po_for_non_courier_products(self):
#     #     """
#     #     Create POs for sale.order lines that are:
#     #       - service products only (product.type == 'service')
#     #       - and NOT courier products (exclude by variant/template)
#     #     """
#     #     PurchaseOrder = self.env["purchase.order"]
#     #     PurchaseOrderLine = self.env["purchase.order.line"]
#     #     CourierCompany = self.env["codeware.courier.company"]
#     #
#     #     # collect courier product ids (both variant ids and template ids)
#     #     courier_companies = CourierCompany.search([])
#     #     courier_variant_ids = set()
#     #     courier_template_ids = set()
#     #     if courier_companies:
#     #         for c in courier_companies:
#     #             prod = c.courier_product_id
#     #             if not prod:
#     #                 continue
#     #             pid = getattr(prod, "id", False)
#     #             if pid:
#     #                 courier_variant_ids.add(int(pid))
#     #             tmpl = getattr(prod, "product_tmpl_id", None)
#     #             if tmpl and getattr(tmpl, "id", False):
#     #                 courier_template_ids.add(int(tmpl.id))
#     #
#     #     courier_variant_ids = [int(x) for x in courier_variant_ids if x]
#     #     courier_template_ids = [int(x) for x in courier_template_ids if x]
#     #
#     #     _logger.debug("Courier variant ids: %s; Courier template ids: %s", courier_variant_ids, courier_template_ids)
#     #
#     #     for order in self:
#     #         # only lines that have a product, are not layout/display, AND are service products
#     #         sale_lines = order.order_line.filtered(
#     #             lambda l: l.product_id and not getattr(l, "display_type", False) and getattr(l.product_id, "type",
#     #                                                                                          "") == "service"
#     #         )
#     #
#     #         if not sale_lines:
#     #             _logger.debug("No service lines to process for sale %s", order.name)
#     #             continue
#     #
#     #         # exclude courier products
#     #         def is_courier(line):
#     #             pid = line.product_id.id
#     #             tmpl_id = getattr(line.product_id, "product_tmpl_id",
#     #                               False) and line.product_id.product_tmpl_id.id or False
#     #             if pid and pid in courier_variant_ids:
#     #                 return True
#     #             if tmpl_id and tmpl_id in courier_template_ids:
#     #                 return True
#     #             return False
#     #
#     #         non_courier_lines = sale_lines.filtered(lambda l: not is_courier(l))
#     #
#     #         excluded_lines = sale_lines - non_courier_lines
#     #         if excluded_lines:
#     #             for ex in excluded_lines:
#     #                 try:
#     #                     _logger.debug(
#     #                         "Excluded courier product from PO creation: sale %s, product %s (variant=%s, template=%s)",
#     #                         order.name,
#     #                         ex.product_id.display_name,
#     #                         ex.product_id.id,
#     #                         getattr(ex.product_id, "product_tmpl_id",
#     #                                 False) and ex.product_id.product_tmpl_id.id or False,
#     #                     )
#     #                 except Exception:
#     #                     _logger.debug("Excluded a courier service line (couldn't read product name) for sale %s",
#     #                                   order.name)
#     #
#     #         if not non_courier_lines:
#     #             _logger.debug("All service lines were courier products or none left for sale %s", order.name)
#     #             continue
#     #
#     #         # group service lines by vendor partner id (use first available seller on variant or template)
#     #         vendor_map = {}
#     #         for line in non_courier_lines:
#     #             product = line.product_id
#     #
#     #             # prefer product-level seller referencing this variant, else any product seller
#     #             seller = None
#     #             if product.seller_ids:
#     #                 seller_candidates = product.seller_ids.filtered(
#     #                     lambda s: not s.product_id or s.product_id.id == product.id)
#     #                 seller = seller_candidates[:1] or product.seller_ids[:1]
#     #                 seller = seller[0] if seller else None
#     #
#     #             # fallback to template-level sellers
#     #             if not seller and product.product_tmpl_id and product.product_tmpl_id.seller_ids:
#     #                 seller = product.product_tmpl_id.seller_ids[:1]
#     #                 seller = seller[0] if seller else None
#     #
#     #             if not seller:
#     #                 _logger.debug(
#     #                     "Skipping service product without supplier: %s (sale %s). Add supplier on product or template to auto-create PO.",
#     #                     product.display_name, order.name
#     #                 )
#     #                 continue
#     #
#     #             # resolve vendor partner record from seller
#     #             vendor_partner = None
#     #             if hasattr(seller, "name") and seller.name:
#     #                 vendor_partner = seller.name
#     #             elif hasattr(seller, "partner_id") and seller.partner_id:
#     #                 vendor_partner = seller.partner_id
#     #             else:
#     #                 vendor_partner = getattr(seller, "partner", None)
#     #
#     #             if not vendor_partner or not vendor_partner.id:
#     #                 _logger.debug("Cannot resolve vendor for service product %s; skipping", product.display_name)
#     #                 continue
#     #
#     #             vendor_map.setdefault(vendor_partner.id, []).append(line)
#     #
#     #         # create/reuse PO per vendor for this sale
#     #         for vendor_id, lines in vendor_map.items():
#     #             po = PurchaseOrder.search([("origin", "=", order.name), ("partner_id", "=", vendor_id)], limit=1)
#     #             if not po:
#     #                 po_vals = {
#     #                     "partner_id": vendor_id,
#     #                     "origin": order.name,
#     #                     "date_order": fields.Datetime.now(),
#     #                     "company_id": order.company_id.id,
#     #                 }
#     #                 po = PurchaseOrder.create(po_vals)
#     #
#     #             for l in lines:
#     #                 # for services prefer product.purchase_uom_id else fallback
#     #                 uom_id = (getattr(l.product_id, "purchase_uom_id", False) and l.product_id.purchase_uom_id.id) or (
#     #                             l.product_uom_id.id or getattr(l.product_id, "uom_id",
#     #                                                            False) and l.product_id.uom_id.id)
#     #                 name = l.product_id.display_name or l.name or l.product_id.name
#     #                 price_unit = float(getattr(l.product_id, "standard_price", 0.0) or 0.0)
#     #
#     #                 try:
#     #                     PurchaseOrderLine.create({
#     #                         "order_id": po.id,
#     #                         "product_id": l.product_id.id,
#     #                         "name": name,
#     #                         "product_qty": l.product_uom_qty,
#     #                         "product_uom_id": uom_id,
#     #                         "price_unit": price_unit,
#     #                         "date_planned": fields.Datetime.now() + timedelta(days=1),
#     #                     })
#     #                     _logger.debug("Created PO line for service product %s on PO %s (sale %s)", name, po.name,
#     #                                   order.name)
#     #                 except Exception:
#     #                     _logger.exception("Failed to create PO line for sale %s, service product %s", order.name,
#     #                                       l.product_id.display_name)
#     #
#     #     return True
#     #
#     #
#     #
#     #
#     # @api.depends("name")
#     # def _compute_purchase_orders(self):
#     #     """Compute purchase orders whose origin == sale.name"""
#     #     Purchase = self.env["purchase.order"]
#     #     for order in self:
#     #         if not order.name:
#     #             order.purchase_order_ids = [(6, 0, [])]
#     #             order.purchase_order_count = 0
#     #             continue
#     #         pos = Purchase.search([("origin", "=", order.name)])
#     #         order.purchase_order_ids = [(6, 0, pos.ids)]
#     #         order.purchase_order_count = len(pos)
#     #
#     # def action_view_purchase_orders(self):
#     #     """
#     #     Open the Purchase Orders in LIST + FORM view (default Odoo behavior):
#     #     - If no PO exists → open empty list (user can create manually)
#     #     - If PO exists → open list of all POs for this SO
#     #     """
#     #     self.ensure_one()
#     #
#     #     action = {
#     #         "name": "Purchase Orders",
#     #         "type": "ir.actions.act_window",
#     #         "res_model": "purchase.order",
#     #         "view_mode": "list,form",
#     #         "domain": [("origin", "=", self.name)],
#     #         "context": {"default_origin": self.name},
#     #         "target": "current",
#     #     }
#     #     return action
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
# # # -*- coding: utf-8 -*-
# # from odoo import models, fields, api
# # from datetime import timedelta
# #
# # class SaleOrder(models.Model):
# #     _inherit = "sale.order"
# #
# #     purchase_order_count = fields.Integer(
# #         string="Purchase Orders", compute="_compute_purchase_orders", store=False
# #     )
# #     purchase_order_ids = fields.Many2many(
# #         "purchase.order", string="Purchase Orders", compute="_compute_purchase_orders"
# #     )
# #
# #     def _action_confirm(self):
# #         res = super()._action_confirm()
# #         for order in self:
# #             order._create_po_for_courier_products()
# #         return res
# #
# #     # def _create_po_for_courier_products(self):
# #     #     PurchaseOrder = self.env["purchase.order"]
# #     #     PurchaseLine = self.env["purchase.order.line"]
# #     #     CourierCompany = self.env["codeware.courier.company"]
# #     #
# #     #     # Get all courier companies
# #     #     courier_companies = CourierCompany.search([])
# #     #
# #     #     # Build a lookup: courier_product_id -> courier company record
# #     #     courier_product_map = {}
# #     #     for company in courier_companies:
# #     #         if company.courier_product_id:
# #     #             courier_product_map[company.courier_product_id.id] = company
# #     #
# #     #     vendor_map = {}  # vendor -> list of sale.order.line
# #     #
# #     #     for line in self.order_line:
# #     #         product = line.product_id
# #     #
# #     #         # Skip if not courier product
# #     #         if product.id not in courier_product_map:
# #     #             continue
# #     #
# #     #         courier_company = courier_product_map[product.id]
# #     #
# #     #         # Only external courier companies create PO
# #     #         if courier_company.internal:
# #     #             continue
# #     #
# #     #         # Product must have seller info
# #     #         if not product.seller_ids:
# #     #             continue
# #     #
# #     #         # pick the first seller entry (you can improve selection logic if needed)
# #     #         seller = product.seller_ids[0]
# #     #         vendor = seller.name if hasattr(seller, "name") else seller.partner_id
# #     #         # normalize vendor partner record
# #     #         if hasattr(vendor, "id"):
# #     #             vendor_partner = vendor
# #     #         else:
# #     #             vendor_partner = seller.partner_id
# #     #
# #     #         vendor_map.setdefault(vendor_partner, []).append(line)
# #     #
# #     #     # No PO needed
# #     #     if not vendor_map:
# #     #         return True
# #     #
# #     #     # Create PO per vendor
# #     #     for vendor, lines in vendor_map.items():
# #     #         po_vals = {
# #     #             "partner_id": vendor.id,
# #     #             "origin": self.name,
# #     #             "date_order": fields.Datetime.now(),
# #     #         }
# #     #         po = PurchaseOrder.create(po_vals)
# #     #
# #     #         for sol in lines:
# #     #             # Use the sale line quantity (or hardcode 1 if courier items are always qty=1)
# #     #             qty = sol.product_uom_qty if hasattr(sol, "product_uom_qty") else 1.0
# #     #             PurchaseLine.create(
# #     #                 {
# #     #                     "order_id": po.id,
# #     #                     "product_id": sol.product_id.id,
# #     #                     "name": sol.product_id.display_name,
# #     #                     "product_qty": qty,
# #     #                     "product_uom_id": sol.product_uom_id.id,
# #     #                     "price_unit": sol.product_id.standard_price,
# #     #                     "date_planned": fields.Datetime.now() + timedelta(days=1),
# #     #                 }
# #     #             )
# #     #
# #     #     return True
# #
# #     def _create_po_for_courier_products(self):
# #         PurchaseOrder = self.env["purchase.order"]
# #         PurchaseOrderLine = self.env["purchase.order.line"]
# #         CourierCompany = self.env["codeware.courier.company"]
# #
# #         # Get all courier products from courier company master
# #         courier_companies = CourierCompany.search([])
# #         courier_product_ids = courier_companies.mapped('courier_product_id').ids
# #
# #         # Collect all sale lines that belong to courier products
# #         courier_lines = self.order_line.filtered(lambda l: l.product_id.id in courier_product_ids)
# #
# #         # If no courier lines, no purchase order is needed
# #         if not courier_lines:
# #             return True
# #
# #         # Use the first courier product's seller to determine vendor
# #         courier_product = courier_lines[0].product_id
# #         seller = courier_product.seller_ids[:1] and courier_product.seller_ids[0] or None
# #         if not seller:
# #             # No supplier info -> cannot create PO
# #             return True
# #
# #         # Robustly fetch the partner record from supplierinfo
# #         vendor_partner = None
# #         if hasattr(seller, 'name') and seller.name:
# #             # older/newer Odoo sometimes uses 'name' field as m2o to partner
# #             vendor_partner = seller.name
# #         elif hasattr(seller, 'partner_id') and seller.partner_id:
# #             vendor_partner = seller.partner_id
# #         else:
# #             # fallback to partner stored directly on supplierinfo (rare)
# #             vendor_partner = getattr(seller, 'partner', None)
# #
# #         if not vendor_partner or not vendor_partner.id:
# #             # can't determine vendor partner
# #             return True
# #
# #         # Create single PO for this vendor
# #         po_vals = {
# #             "partner_id": vendor_partner.id,
# #             "origin": self.name,
# #             "date_order": fields.Datetime.now(),
# #         }
# #         po = PurchaseOrder.create(po_vals)
# #
# #         # Create PO lines for each courier sale line
# #         for line in courier_lines:
# #             qty = getattr(line, 'product_uom_qty', 1.0)
# #             PurchaseOrderLine.create({
# #                 "order_id": po.id,
# #                 "product_id": line.product_id.id,
# #                 "name": line.product_id.display_name or line.name or line.product_id.name,
# #                 "product_qty": qty,
# #                 "product_uom_id": line.product_uom_id.id or line.product_id.uom_id.id,
# #                 "price_unit": line.product_id.standard_price or 0.0,
# #                 "date_planned": fields.Datetime.now() + timedelta(days=1),
# #             })
# #
# #         return True
# #
# #     @api.depends("name")
# #     def _compute_purchase_orders(self):
# #         """Compute purchase orders whose origin == sale.name"""
# #         Purchase = self.env["purchase.order"]
# #         for order in self:
# #             if not order.name:
# #                 order.purchase_order_ids = [(6, 0, [])]
# #                 order.purchase_order_count = 0
# #                 continue
# #             pos = Purchase.search([("origin", "=", order.name)])
# #             order.purchase_order_ids = [(6, 0, pos.ids)]
# #             order.purchase_order_count = len(pos)
# #
# #     def action_view_purchase_orders(self):
# #         """Open only the purchase order form:
# #         - no PO -> open new PO form to create one (default_origin set)
# #         - exists -> open form of the first matched PO
# #         """
# #         self.ensure_one()
# #         Purchase = self.env["purchase.order"]
# #         # prefer opening the first PO found; if you prefer latest use order="id desc", limit=1
# #         pos = Purchase.search([("origin", "=", self.name)], order="id asc")
# #         form_view = self.env.ref("purchase.view_purchase_order_form", False)
# #
# #         if not pos:
# #             return {
# #                 "name": "New Purchase Order",
# #                 "type": "ir.actions.act_window",
# #                 "res_model": "purchase.order",
# #                 "view_mode": "form",
# #                 "views": [(form_view.id, "form")] if form_view else [(False, "form")],
# #                 "target": "current",
# #                 "context": {"default_origin": self.name},
# #             }
# #
# #         first_po = pos[0]
# #         return {
# #             "name": "Purchase Order",
# #             "type": "ir.actions.act_window",
# #             "res_model": "purchase.order",
# #             "res_id": first_po.id,
# #             "view_mode": "form",
# #             "views": [(form_view.id, "form")] if form_view else [(False, "form")],
# #             "target": "current",
# #             "context": {"default_origin": self.name},
# #         }
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# # # from odoo import models, fields,api
# # # from datetime import timedelta
# # #
# # #
# # # class SaleOrder(models.Model):
# # #     _inherit = "sale.order"
# # #     purchase_order_count = fields.Integer(
# # #         string="Purchase Orders", compute="_compute_purchase_orders", store=False
# # #     )
# # #     purchase_order_ids = fields.Many2many(
# # #         "purchase.order", string="Purchase Orders", compute="_compute_purchase_orders"
# # #     )
# # #
# # #
# # #     def _action_confirm(self):
# # #         res = super()._action_confirm()
# # #         for order in self:
# # #             order._create_po_for_courier_products()
# # #         return res
# # #
# # #     def _create_po_for_courier_products(self):
# # #         PurchaseOrder = self.env['purchase.order']
# # #         PurchaseLine = self.env['purchase.order.line']
# # #         CourierCompany = self.env['codeware.courier.company']
# # #
# # #         # Get all courier companies
# # #         courier_companies = CourierCompany.search([])
# # #
# # #         # Build a lookup: product_id -> courier company
# # #         courier_product_map = {}
# # #         for company in courier_companies:
# # #             if company.courier_product_id:
# # #                 courier_product_map[company.courier_product_id.id] = company
# # #
# # #         vendor_map = {}  # vendor → sale order lines
# # #
# # #         for line in self.order_line:
# # #             product = line.product_id
# # #
# # #             # Check if product is courier company product
# # #             if product.id not in courier_product_map:
# # #                 continue
# # #
# # #             courier_company = courier_product_map[product.id]
# # #
# # #             # Only external courier companies create PO
# # #             if courier_company.internal:
# # #                 continue
# # #
# # #             # Product must have vendor
# # #             if not product.seller_ids:
# # #                 continue
# # #
# # #             vendor = product.seller_ids[0].partner_id
# # #
# # #             vendor_map.setdefault(vendor, []).append(line)
# # #
# # #         # No PO needed
# # #         if not vendor_map:
# # #             return True
# # #
# # #         # Create PO per vendor
# # #         for vendor, lines in vendor_map.items():
# # #
# # #             po = PurchaseOrder.create({
# # #                 'partner_id': vendor.id,
# # #                 'origin': self.name,
# # #                 'date_order': fields.Datetime.now(),
# # #             })
# # #
# # #             for sol in lines:
# # #                 PurchaseLine.create({
# # #                     'order_id': po.id,
# # #                     'product_id': sol.product_id.id,
# # #                     'name': sol.product_id.display_name,
# # #                     'product_qty': 1,
# # #                     'product_uom_id': sol.product_uom_id.id,
# # #                     'price_unit': sol.product_id.standard_price,
# # #                     'date_planned': fields.Datetime.now() + timedelta(days=1),
# # #                 })
# # #
# # #         return True
# # #
# # #     @api.depends()  # no depend fields because we search by origin/name
# # #     def _compute_purchase_orders(self):
# # #         Purchase = self.env["purchase.order"]
# # #         for order in self:
# # #             if not order.name:
# # #                 order.purchase_order_ids = [(0, 0)]
# # #                 order.purchase_order_count = 0
# # #                 continue
# # #             pos = Purchase.search([("origin", "=", order.name)])
# # #             order.purchase_order_ids = [(6, 0, pos.ids)]
# # #             order.purchase_order_count = len(pos)
# # #
# # #     def action_view_purchase_orders(self):
# # #         """Open purchase orders created for this sale (search by origin == sale.name)."""
# # #         self.ensure_one()
# # #         action = {
# # #             "name": "Purchase Orders",
# # #             "type": "ir.actions.act_window",
# # #             "res_model": "purchase.order",
# # #             "view_mode": "tree,form",
# # #             # domain filters to the POs whose origin equals this sale order name
# # #             "domain": [("origin", "=", self.name)],
# # #             "context": {"default_origin": self.name},
# # #         }
# # #         return action
# # #
# # #     def action_view_purchase_orders(self):
# # #         """Open purchase orders created for this sale (search by origin == sale.name)."""
# # #         self.ensure_one()
# # #         # prefer 'list' instead of 'tree' (Odoo 18 / your codebase uses list views)
# # #         action = {
# # #             "name": "Purchase Orders",
# # #             "type": "ir.actions.act_window",
# # #             "res_model": "purchase.order",
# # #             "view_mode": "list,form",
# # #             # explicit views helps the client pick the right view types
# # #             # if you want to force specific view ids, replace the list below with actual view ids:
# # #             # "views": [(list_view_id, 'list'), (form_view_id, 'form')],
# # #             "domain": [("origin", "=", self.name)],
# # #             "context": {"default_origin": self.name},
# # #         }
# # #         return action
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# #
# # from odoo import models, fields, api
# #
# # class SaleOrder(models.Model):
# #     _inherit = 'sale.order'
# #
#     # def _action_confirm(self):
#     #     res = super()._action_confirm()
#     #
#     #     for order in self:
#     #         # Request may link through request_id OR origin field
#     #         req = order.request_id
#     #         if not req and order.origin:
#     #             req = self.env['codeware.request'].search([('name', '=', order.origin)], limit=1)
#     #
#     #         if req:
#     #             for picking in order.picking_ids:
#     #                 picking.receiver_name = req.customer_name
#     #                 picking.receiver_phone = req.receiver_phone_partner or req.receiver_phone
#     #                 picking.receiver_address = req.customer_address
#     #                 picking.receiver_zip = req.dest_zip
#     #                 # Copy serviced by into the delivery
#     #                 picking.picking_serviced_by_id = req.serviced_by_id
#     #
#     #     return res
# #
# # #
# # #