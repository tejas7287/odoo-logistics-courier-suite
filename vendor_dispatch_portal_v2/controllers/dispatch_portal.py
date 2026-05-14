from odoo import http
from datetime import datetime
from odoo.http import request
from werkzeug.exceptions import Forbidden


class VendorDispatchPortal(http.Controller):

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------
    def _is_vendor_user(self, user):
        return (
            user.has_group('base.group_portal')
            and user.partner_id
            and user.partner_id.vendor_portal
        )

    # ---------------------------------------------------------
    # LIST PAGE  → /my/vendor_orders
    # ---------------------------------------------------------
    @http.route(['/my/vendor_orders'], type='http', auth='user', website=True)
    def vendor_orders(self, **kw):
        user = request.env.user
        partner = user.partner_id
        Picking = request.env['stock.picking'].sudo()

        if self._is_vendor_user(user):
            pickings = Picking.search(
                [('partner_id', '=', partner.id)],
                order='write_date desc'
            )
        elif user.has_group('base.group_system'):
            pickings = Picking.search([], order='write_date desc')
        else:
            pickings = Picking.search(
                [('vendor_sale_order_id.partner_id', '=', partner.id)],
                order='write_date desc'
            )

        return request.render(
            'vendor_dispatch_portal_v2.portal_vendor_dispatch_list',
            {'pickings': pickings}
        )

    # ---------------------------------------------------------
    # DETAIL PAGE → /my/vendor_dispatch/<id>
    # ---------------------------------------------------------
    @http.route(
        ['/my/vendor_dispatch/<int:picking_id>'],
        type='http', auth='user', website=True
    )
    def vendor_dispatch_detail(self, picking_id, **kw):

        picking = request.env['stock.picking'].sudo().browse(picking_id)

        if not picking.exists():
            return request.not_found()

        return request.render(
            'vendor_dispatch_portal_v2.vendor_dispatch_detail_page',
            {
                'picking': picking,
                'is_vendor': request.env.user.has_group('base.group_portal'),
            }
        )

    # ---------------------------------------------------------
    # SUBMIT
    # ---------------------------------------------------------
    @http.route(
        ['/my/vendor_orders/submit/<int:picking_id>'],
        type='http', auth='user', website=True, methods=['POST']
    )
    def submit_dispatch(self, picking_id, **post):
        user = request.env.user
        picking = request.env['stock.picking'].sudo().browse(picking_id)

        if not picking.exists() or not self._is_vendor_user(user):
            raise Forbidden()

        # Parse datetime-local
        vendor_date = post.get('vendor_dispatch_date')
        if vendor_date:
            try:
                post['vendor_dispatch_date'] = datetime.strptime(
                    vendor_date, '%Y-%m-%dT%H:%M'
                ).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                post.pop('vendor_dispatch_date', None)

        vals = {
             'vendor_dispatch_reference': post.get('vendor_dispatch_reference'),
            'vendor_dispatch_date': post.get('vendor_dispatch_date'),
            'vendor_carrier_name': post.get('vendor_carrier_name'),
            'vendor_tracking_number': post.get('vendor_tracking_number'),
            'vendor_notes': post.get('vendor_notes'),
            'vendor_invoice_number': post.get('vendor_invoice_number'),
            'vendor_payment_status': post.get('vendor_payment_status'),
            'vendor_delivery_status': post.get('vendor_delivery_status'),
            'vendor_dispatch_location_id': int(post.get('vendor_dispatch_location_id')) if post.get(
            'vendor_dispatch_location_id') else False,
            'vendor_expected_delivery_date': post.get('vendor_expected_delivery_date'),
            'vendor_carrier_id': int(post.get('vendor_carrier_id')) if post.get('vendor_carrier_id') else False,}

        picking._update_from_vendor_submission(vals)

        return request.redirect('/my/vendor_orders?success=1')



























