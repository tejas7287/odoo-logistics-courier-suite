from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import UserError
from odoo.exceptions import AccessDenied


class VendorAcknowledgePortal(CustomerPortal):


    @http.route(['/my/vendor_acknowledgements'], type='http', auth='user', website=True)
    def portal_ack_list(self, **kw):

        partner = request.env.user.partner_id
        portal_location = partner.portal_location_id
        mode = kw.get('mode', 'ack')  # DEFAULT = ack

        # ❌ NO LOCATION
        if not portal_location:
            return request.render(
                'vendor_dispatch_portal_v2.portal_vendor_acknowledgement_list',
                {
                    'pickings': [],
                    'picking_types': [],
                    'mode': mode,
                }
            )

        # ================================
        # 🔍 SEARCH (ONLY ADDITION)
        # ================================
        tracking_search = (kw.get('tracking') or '').strip()

        # ================================
        # ✅ EXISTING DOMAIN (UNCHANGED)
        # ================================
        domain = [
            ('location_dest_id', '=', portal_location.id),
            ('vendor_portal_state', 'in', ['draft', 'done']),
            ('state','=', 'done')
        ]

        # ✅ SAFE FILTER (ONLY IF SEARCHED)
        if tracking_search:
            domain.append(('tracking_number', 'ilike', tracking_search))

        # ✅ SINGLE SEARCH (IMPORTANT)
        pickings = request.env['stock.picking'].sudo().search(domain,order='id desc')

        # ================================
        # ✅ EXISTING PICKING TYPES
        # ================================
        picking_types = request.env['stock.picking.type'].sudo().search([
            ('default_location_src_id', '=', portal_location.id)
        ])

        return request.render(
            'vendor_dispatch_portal_v2.portal_vendor_acknowledgement_list',
            {
                'pickings': pickings,
                'picking_types': picking_types,
                'mode': mode,
                'tracking_search': tracking_search,  # 👈 REQUIRED FOR TEMPLATE
                'error': kw.get('error'),
                'success': kw.get('success'),
            }
        )

    # --------------------------------------------------
    # BULK PROCESS (DRAFT → DONE)
    # --------------------------------------------------

    @http.route(
        ['/my/vendor_acknowledgements/process'],
        type='http',
        auth='user',
        website=True,
        methods=['POST']
    )
    def portal_bulk_process(self, **post):

        partner = request.env.user.partner_id
        location = partner.portal_location_id

        if not location:
            return request.redirect(
                '/my/vendor_acknowledgements?msg=no_location'
            )

        # picking_ids = post.get('picking_ids')
        picking_ids = request.httprequest.form.getlist('picking_ids[]')

        picking_type_id = post.get('picking_type_id')

        # ❌ NO DELIVERY SELECTED
        # if not picking_ids:
        #     return request.redirect(
        #         '/my/vendor_acknowledgements?msg=no_selection'
        #     )
        picking_ids = [int(pid) for pid in picking_ids]

        if isinstance(picking_ids, str):
            picking_ids = [int(x) for x in picking_ids.split(',') if x]

        # Fetch ALL selected deliveries (draft + done)
        pickings = request.env['stock.picking'].sudo().search([
            ('id', 'in', picking_ids),
            ('location_dest_id', '=', location.id),
        ])

        # ⚠️ ALREADY VALIDATED
        # already_done = pickings.filtered(
        #     lambda p: p.vendor_portal_state == 'done'
        # )
        # if already_done:
        #     return request.redirect(
        #         '/my/vendor_acknowledgements?msg=already_done'
        #     )



        # ❌ NO OPERATION SELECTED
        if not picking_type_id:
            return request.redirect(
                '/my/vendor_acknowledgements?msg=no_operation'
            )

        picking_type = request.env['stock.picking.type'].sudo().browse(
            int(picking_type_id)
        )

        # ✅ PROCESS ONLY DRAFT DELIVERIES
        for picking in pickings.filtered(
                lambda p: p.vendor_portal_state == 'draft'
        ):

            if not picking.move_ids:
                continue

            new_picking = request.env['stock.picking'].sudo().create({
                'picking_type_id': picking_type.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'origin': picking.name,
            })

            for move in picking.move_ids:
                request.env['stock.move'].sudo().create({
                    'picking_id': new_picking.id,
                    'product_id': move.product_id.id,
                    'product_uom_qty': move.product_uom_qty,
                    'product_uom': move.product_uom.id,
                    'location_id': new_picking.location_id.id,
                    'location_dest_id': new_picking.location_dest_id.id,
                })

            new_picking.action_confirm()
            new_picking.button_validate()

            picking.vendor_portal_state = 'done'

        return request.redirect(
            '/my/vendor_acknowledgements?mode=operation&success=1'
        )


    @http.route(
        ['/my/vendor_acknowledgements/delete'],
        type='http',
        auth='user',
        website=True,
        methods=['POST']
    )
    def portal_bulk_delete(self, **post):

        partner = request.env.user.partner_id
        picking_ids = post.get('picking_ids')

        if not picking_ids:
            return request.redirect(
                '/my/vendor_acknowledgements?msg=no_delete_selection'
            )

        if isinstance(picking_ids, str):
            picking_ids = [int(x) for x in picking_ids.split(',') if x]

        pickings = request.env['stock.picking'].sudo().browse(picking_ids)

        delete_count = len(pickings)

        pickings.unlink()

        # ✅ DECREASE COUNT (never below zero)
        new_count = max(
            partner.vendor_ack_count - delete_count,
            0
        )
        partner.sudo().write({
            'vendor_ack_count': new_count
        })

        return request.redirect(
            '/my/vendor_acknowledgements?success=deleted'
        )

    @http.route(
        ['/my/vendor_acknowledgements/<int:picking_id>'],
        type='http',
        auth='user',
        website=True
    )
    def portal_ack_form(self, picking_id, **kw):
        partner = request.env.user.partner_id

        picking = request.env['stock.picking'].sudo().browse(picking_id)

        # 🔐 SECURITY: allow only own location deliveries
        if not picking or picking.location_dest_id != partner.portal_location_id:
            return request.redirect('/my/vendor_acknowledgements')

        return request.render(
            'vendor_dispatch_portal_v2.portal_vendor_acknowledgement_form',
            {
                'picking': picking
            }
        )


    @http.route(
        ['/my/vendor_acknowledgements/ack/<int:picking_id>'],
        type='http',
        auth='user',
        website=True,
        methods=['POST']
    )
    def portal_ack_action(self, picking_id, **post):

        partner = request.env.user.partner_id
        picking = request.env['stock.picking'].sudo().browse(picking_id)

        # 🔒 Safety check
        if picking.location_dest_id != partner.portal_location_id:
            return request.redirect('/my/vendor_acknowledgements')

        # ✅ COUNT ONLY FIRST TIME
        if not picking.portal_acknowledged:
            partner.sudo().write({
                'vendor_ack_count': partner.vendor_ack_count + 1
            })
            picking.sudo().write({
                'portal_acknowledged': True
            })

        return request.redirect(
            '/my/vendor_acknowledgements?success=ack'
        )





########################

class CustomerTrackingPortal(http.Controller):
    @http.route(
        ['/my/trackings'],
        type='http',
        auth='user',
        website=True
    )
    def customer_tracking_list(self, **kw):
        partner = request.env.user.partner_id

        # Customer's deliveries only
        pickings = request.env['stock.picking'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '!=', 'cancel'),
        ], order='id desc')

        return request.render(
            'vendor_dispatch_portal_v2.portal_customer_tracking_list',
            {
                'pickings': pickings
            }
        )

    @http.route(
        ['/my/trackings/<int:picking_id>'],
        type='http',
        auth='user',
        website=True
    )
    def customer_tracking(self, picking_id, **kw):
        picking = request.env['stock.picking'].sudo().browse(picking_id)

        # 🔐 Security
        if not picking or picking.partner_id != request.env.user.partner_id:
            return request.redirect('/my/trackings')

        return request.render(
            'vendor_dispatch_portal_v2.portal_customer_tracking_form',
            {
                'picking': picking
            }
        )

    @http.route(['/my/stock/cards'], type='http', auth='user', website=True)
    def portal_stock_cards(self, **kw):
        partner = request.env.user.partner_id
        if not partner.portal_location_id:
            raise AccessDenied()

        domain = [
            ('delivery_acknowledged', '=', True),
            ('vendor_portal_state', '=', 'draft'),  # 🔥 CRITICAL FIX
            ('location_dest_id', 'child_of', partner.portal_location_id.id),
        ]

        pickings = request.env['stock.picking'].sudo().search(domain,order='id desc')
        total_orders = len(pickings)

        return request.render(
            'vendor_dispatch_portal_v2.portal_stock_card_page',
            {
                'pickings': pickings,
                'total_orders': total_orders,
            }
        )