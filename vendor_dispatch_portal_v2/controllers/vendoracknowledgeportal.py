from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import UserError
from odoo.exceptions import AccessDenied
from odoo.osv import expression



class VendorAcknowledgePortal(CustomerPortal):

    @http.route(['/my/vendor_acknowledgements'], type='http', auth='user', website=True)
    def portal_ack_list(self, **kw):

        partner = request.env.user.partner_id
        portal_location = partner.portal_location_id
        mode = kw.get('mode', 'ack')

        if not portal_location:
            return request.render(
                'vendor_dispatch_portal_v2.portal_vendor_acknowledgement_list',
                {'pickings': [], 'mode': mode}
            )

        # -----------------------------
        # SEARCH
        # -----------------------------
        tracking_search = (kw.get('tracking') or '').strip()
        handoff_search = (kw.get('handoff_ref') or '').strip()

        domain = [
            ('location_dest_id', '=', portal_location.id),
            ('vendor_portal_state', 'in', ['draft', 'done']),
            ('state', '=', 'done'),
        ]

        if tracking_search:
            domain.append(('tracking_number', 'ilike', tracking_search))

        if handoff_search:
            domain.append(('handoff_ref', 'ilike', handoff_search))

        Picking = request.env['stock.picking'].sudo()

        # -----------------------------
        # PAGINATION (FOR ALL MODES)
        # -----------------------------
        page = int(kw.get('page', 1))
        per_page = 15
        offset = (page - 1) * per_page

        total_count = Picking.search_count(domain)

        pickings = Picking.search(
            domain,
            limit=per_page,
            offset=offset,
            order="id desc"
        )

        total_pages = max(1, (total_count + per_page - 1) // per_page)

        max_pages = 8
        start_page = max(1, page - (max_pages // 2))
        end_page = min(total_pages, start_page + max_pages - 1)
        start_page = max(1, end_page - max_pages + 1)

        picking_types = request.env['stock.picking.type'].sudo().search([
            ('default_location_src_id', '=', portal_location.id)
        ])

        return request.render(
            'vendor_dispatch_portal_v2.portal_vendor_acknowledgement_list',
            {
                'pickings': pickings,
                'picking_types': picking_types,
                'mode': mode,
                'tracking_search': tracking_search,
                "handoff_search": handoff_search,

                # pagination
                'page': page,
                'total_pages': total_pages,
                'page_range': list(range(start_page, end_page + 1)),
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

                # 🔥 PROPAGATE TRACKING
                'tracking_number': picking.tracking_number,
                'carrier_id': picking.carrier_id.id if picking.carrier_id else False,
            })



            # new_picking = request.env['stock.picking'].sudo().create({
            #     'picking_type_id': picking_type.id,
            #     'location_id': picking_type.default_location_src_id.id,
            #     'location_dest_id': picking_type.default_location_dest_id.id,
            #     'origin': picking.name,
            # })

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

        mode = post.get('mode')

        if mode == 'operation':
            return request.redirect('/my/vendor_acknowledgements?mode=operation&success=1')
        else:
            return request.redirect('/my/vendor_acknowledgements?success=ack')


# DO NOT DELETE MAN NEVER

# class CustomerTrackingPortal(http.Controller):
#
#     @http.route(
#         ['/my/trackings', '/my/trackings/page/<int:page>'],
#         type='http',
#         auth='user',
#         website=True
#     )
#
#     def customer_tracking_list(self, page=1, **kw):
#         page = int(page)
#         page_size = 10
#
#         partner = request.env.user.partner_id
#         domain = [
#             ('partner_id', '=', partner.id),
#             ('state', '!=', 'cancel'),
#         ]
#
#         Picking = request.env['stock.picking'].sudo()
#         total = Picking.search_count(domain)
#         total_pages = max(1, (total + page_size - 1) // page_size)
#
#         pickings = Picking.search(
#             domain,
#             limit=page_size,
#             offset=(page - 1) * page_size,
#             order='id desc'
#         )
#
#         return request.render(
#             'vendor_dispatch_portal_v2.portal_customer_tracking_list',
#             {
#                 'pickings': pickings,
#                 'page': page,
#                 'total_pages': total_pages,
#             }
#         )
#
#     @http.route(
#         ['/my/trackings/<int:picking_id>'],
#         type='http',
#         auth='user',
#         website=True
#     )
#     def customer_tracking(self, picking_id, **kw):
#
#         picking = request.env['stock.picking'].sudo().browse(picking_id)
#
#         if not picking.exists() or picking.partner_id != request.env.user.partner_id:
#             return request.redirect('/my/trackings')
#
#         return request.render(
#             'vendor_dispatch_portal_v2.portal_customer_tracking_form',
#             {
#                 'picking': picking
#             }
#         )
#
#     @http.route(['/my/stock/cards'], type='http', auth='user', website=True)
#     def portal_stock_cards(self, **kw):
#         partner = request.env.user.partner_id
#         if not partner.portal_location_id:
#             raise AccessDenied()
#
#         domain = [
#             ('delivery_acknowledged', '=', True),
#             ('vendor_portal_state', '=', 'draft'),
#             ('location_dest_id', 'child_of', partner.portal_location_id.id),
#         ]
#
#         pickings = request.env['stock.picking'].sudo().search(domain)
#         total_orders = len(pickings)
#
#         return request.render(
#             'vendor_dispatch_portal_v2.portal_stock_card_page',
#             {
#                 'pickings': pickings,
#                 'total_orders': total_orders,
#             }
#         )

class CustomerTrackingPortal(http.Controller):

    @http.route(
        ['/my/trackings', '/my/trackings/page/<int:page>'],
        type='http',
        auth='user',
        website=True
    )

    def customer_tracking_list(self, page=1, **kw):
        page = int(page)
        page_size = 10

        partner = request.env.user.partner_id
        domain = expression.AND([
            [('state', '!=', 'cancel')],
            expression.OR([
                [('partner_id', '=', partner.id)],  # normal delivery
                [('sale_id.partner_id', '=', partner.id)],  # dropship / website orders
            ])
        ])

        Picking = request.env['stock.picking'].sudo()
        total = Picking.search_count(domain)
        total_pages = max(1, (total + page_size - 1) // page_size)

        pickings = Picking.search(
            domain,
            limit=page_size,
            offset=(page - 1) * page_size,
            order='id desc'
        )

        return request.render(
            'vendor_dispatch_portal_v2.portal_customer_tracking_list',
            {
                'pickings': pickings,
                'page': page,
                'total_pages': total_pages,
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
        partner = request.env.user.partner_id

        if not picking.exists():
            return request.redirect('/my/trackings')

        # ✅ Allow access if:
        # - normal delivery (partner_id)
        # - dropship / website order (sale_id.partner_id)
        if not (
                picking.partner_id == partner
                or picking.sale_id.partner_id == partner
        ):
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
            ('vendor_portal_state', '=', 'draft'),
            ('location_dest_id', 'child_of', partner.portal_location_id.id),
        ]

        pickings = request.env['stock.picking'].sudo().search(domain)
        total_orders = len(pickings)

        return request.render(
            'vendor_dispatch_portal_v2.portal_stock_card_page',
            {
                'pickings': pickings,
                'total_orders': total_orders,
            }
        )
