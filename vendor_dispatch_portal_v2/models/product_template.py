from odoo import models, api, fields


class ProductTemplate(models.Model):
    _inherit = "product.template"

    enable_dropship = fields.Boolean(string="Dropship")

    # ------r---------------------------------------------------
    # ROUTE ENFORCEMENT (❌ DO NOT CHANGE – AS IS)
    # ---------------------------------------------------------
    def _enforce_dropship_route(self):
        dropship_route = self.env.ref(
            "stock_dropshipping.route_drop_shipping",
            raise_if_not_found=False
        )
        if not dropship_route:
            return

        for template in self:
            qty = template.qty_available
            has_route = dropship_route in template.route_ids

            # ❌ Boolean OFF → always remove
            if not template.enable_dropship:
                if has_route:
                    template.with_context(skip_dropship_enforce=True).sudo().write({
                        "route_ids": [(3, dropship_route.id)]
                    })
                continue

            # ❌ Stock available → remove (even if boolean ON)
            if template.enable_dropship and qty > 0:
                if has_route:
                    template.with_context(skip_dropship_enforce=True).sudo().write({
                        "route_ids": [(3, dropship_route.id)]
                    })
                continue

            # ✅ Boolean ON + qty = 0 → ensure route exists
            if template.enable_dropship and qty <= 0 and not has_route:
                template.with_context(skip_dropship_enforce=True).sudo().write({
                    "route_ids": [(4, dropship_route.id)]
                })

    # ---------------------------------------------------------
    # 🔥 TAG WRITE LOGIC (INCORPORATED – NO LOGIC CHANGE ABOVE)
    # ---------------------------------------------------------
    def _sync_dropship_tag(self):
        dropship_route = self.env.ref(
            "stock_dropshipping.route_drop_shipping",
            raise_if_not_found=False
        )
        if not dropship_route:
            return

        tag = self.env["product.tag"].search(
            [("name", "=", "Dropship")],
            limit=1
        )
        if not tag:
            tag = self.env["product.tag"].sudo().create({
                "name": "Dropship"
            })

        for template in self:
            has_route = dropship_route in template.route_ids

            # ADD tag
            if has_route and tag not in template.product_tag_ids:
                template.with_context(skip_dropship_enforce=True).sudo().write({
                    "product_tag_ids": [(4, tag.id)]
                })

            # REMOVE tag
            if not has_route and tag in template.product_tag_ids:
                template.with_context(skip_dropship_enforce=True).sudo().write({
                    "product_tag_ids": [(3, tag.id)]
                })

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._enforce_dropship_route()
        records._sync_dropship_tag()
        return records

    # ---------------------------------------------------------
    # WRITE
    # ---------------------------------------------------------
    def write(self, vals):
        if self.env.context.get("skip_dropship_enforce"):
            return super().write(vals)

        res = super().write(vals)

        # 🔒 SAME TRIGGERS – NO CHANGE
        if "enable_dropship" in vals or "route_ids" in vals:
            self._enforce_dropship_route()
            self._sync_dropship_tag()

        return res


# =========================================================
# STOCK RULE (UNCHANGED)
# =========================================================
class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_rule(self, product_id, location_id, values):
        if values.get("force_dropship"):
            dropship_route = self.env.ref(
                "stock_dropshipping.route_drop_shipping",
                raise_if_not_found=False
            )
            if dropship_route:
                return self.search([
                    ("route_id", "=", dropship_route.id),
                    ("action", "=", "buy"),
                ], limit=1)

        return super()._get_rule(product_id, location_id, values)

    def _prepare_procurement_values(self, procurement):
        values = super()._prepare_procurement_values(procurement)

        if procurement.values.get("force_qty"):
            values["product_qty"] = procurement.values["force_qty"]

        return values


# =========================================================
# STOCK QUANT (UNCHANGED LOGIC + TAG SYNC)
# =========================================================
class StockQuant(models.Model):
    _inherit = "stock.quant"



    def write(self, vals):
        res = super().write(vals)

        # 🔒 Avoid infinite loops when routes write back
        if self.env.context.get("skip_dropship_enforce"):
            return res

        # Only react to REAL stock changes
        if "quantity" not in vals and "inventory_quantity" not in vals:
            return res

        # Only internal stock matters (returns go here)
        internal_quants = self.filtered(
            lambda q: q.location_id.usage == "internal"
        )
        if not internal_quants:
            return res

        # Collect affected templates
        templates = internal_quants.mapped(
            "product_id.product_tmpl_id"
        )

        if not templates:
            return res

        # 🔥 REUSE EXISTING LOGIC — NO CHANGES
        templates.with_context(
            skip_dropship_enforce=True
        )._enforce_dropship_route()

        templates.with_context(
            skip_dropship_enforce=True
        )._sync_dropship_tag()

        return res






























#
# from odoo import models, api, fields
#
#
# class ProductTemplate(models.Model):
#     _inherit = "product.template"
#
#     enable_dropship = fields.Boolean(string="Dropship")
#
#     def _enforce_dropship_route(self):
#         dropship_route = self.env.ref(
#             "stock_dropshipping.route_drop_shipping",
#             raise_if_not_found=False
#         )
#         if not dropship_route:
#             return
#
#         for template in self:
#             qty = template.qty_available
#             has_route = dropship_route in template.route_ids
#
#             # ❌ Boolean OFF → always remove
#             if not template.enable_dropship:
#                 if has_route:
#                     template.with_context(skip_dropship_enforce=True).sudo().write({
#                         "route_ids": [(3, dropship_route.id)]
#                     })
#                 continue
#
#             # ❌ Stock available → remove (even if boolean ON)
#             if template.enable_dropship and qty > 0:
#                 if has_route:
#                     template.with_context(skip_dropship_enforce=True).sudo().write({
#                         "route_ids": [(3, dropship_route.id)]
#                     })
#                 continue
#
#             # ✅ Boolean ON + qty = 0 → ensure route exists
#             if template.enable_dropship and qty <= 0 and not has_route:
#                 template.with_context(skip_dropship_enforce=True).sudo().write({
#                     "route_ids": [(4, dropship_route.id)]
#                 })
#
#     # ---------------------------------------------------------
#     # CREATE
#     # ---------------------------------------------------------
#     @api.model_create_multi
#     def create(self, vals_list):
#         records = super().create(vals_list)
#         records._enforce_dropship_route()
#         return records
#
#     # ---------------------------------------------------------
#     # WRITE
#     # ---------------------------------------------------------
#     def write(self, vals):
#         if self.env.context.get("skip_dropship_enforce"):
#             return super().write(vals)
#
#         res = super().write(vals)
#
#         # 🔒 ONLY boolean or routes trigger enforcement
#         if "enable_dropship" in vals or "route_ids" in vals:
#             self._enforce_dropship_route()
#
#         return res
#
#
#
# from odoo import models
#
#
# class StockRule(models.Model):
#     _inherit = "stock.rule"
#
#     def _get_rule(self, product_id, location_id, values):
#         # 🔥 Force dropship ONLY when explicitly requested
#         if values.get("force_dropship"):
#             dropship_route = self.env.ref(
#                 "stock_dropshipping.route_drop_shipping",
#                 raise_if_not_found=False
#             )
#             if dropship_route:
#                 return self.search([
#                     ("route_id", "=", dropship_route.id),
#                     ("action", "=", "buy"),
#                 ], limit=1)
#
#         return super()._get_rule(product_id, location_id, values)
#
#
#     def _prepare_procurement_values(self, procurement):
#         values = super()._prepare_procurement_values(procurement)
#
#         # Force qty (for split)
#         if procurement.values.get("force_qty"):
#             values["product_qty"] = procurement.values["force_qty"]
#
#         return values
#
#
# class StockQuant(models.Model):
#     _inherit = "stock.quant"
#
#     def write(self, vals):
#         res = super().write(vals)
#
#         if "quantity" in vals or "inventory_quantity" in vals:
#             templates = self.mapped("product_id.product_tmpl_id")
#             templates._enforce_dropship_route()
#
#         return res










# from odoo import models, api
#
#
# class ProductTemplate(models.Model):
#     _inherit = "product.template"
#
#     # ---------------------------------------------------------
#     # SYNC DROPSHIP TAG WITH ROUTE (ADD / REMOVE)
#     # ---------------------------------------------------------
#     def _sync_dropship_variant_tag(self):
#         dropship_route = self.env.ref(
#             "stock_dropshipping.route_drop_shipping",
#             raise_if_not_found=False
#         )
#         if not dropship_route:
#             return
#
#         tag = self.env["product.tag"].search(
#             [("name", "=", "Dropship")],
#             limit=1
#         )
#         if not tag:
#             # create only when needed (when adding)
#             tag = self.env["product.tag"].sudo().create({
#                 "name": "Dropship"
#             })
#
#         for template in self:
#             has_dropship = dropship_route in template.route_ids
#
#             for variant in template.product_variant_ids:
#                 # -------------------------------
#                 # ADD TAG
#                 # -------------------------------
#                 if has_dropship and tag.id not in variant.product_tag_ids.ids:
#                     variant.with_context(
#                         skip_dropship_tag_sync=True
#                     ).sudo().write({
#                         "product_tag_ids": [(4, tag.id)]
#                     })
#
#                 # -------------------------------
#                 # REMOVE TAG
#                 # -------------------------------
#                 if not has_dropship and tag.id in variant.product_tag_ids.ids:
#                     variant.with_context(
#                         skip_dropship_tag_sync=True
#                     ).sudo().write({
#                         "product_tag_ids": [(3, tag.id)]
#                     })
#
#     # ---------------------------------------------------------
#     # CREATE
#     # ---------------------------------------------------------
#     @api.model_create_multi
#     def create(self, vals_list):
#         records = super().create(vals_list)
#         records._sync_dropship_variant_tag()
#         return records
#
#     # ---------------------------------------------------------
#     # WRITE
#     # ---------------------------------------------------------
#     def write(self, vals):
#         # Prevent recursive loop
#         if self.env.context.get("skip_dropship_tag_sync"):
#             return super().write(vals)
#
#         res = super().write(vals)
#
#         if "route_ids" in vals:
#             self._sync_dropship_variant_tag()
#
#         return res
