# models/post_init.py
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def post_init_hook(cr, registry):
    """
    Post-install/upgrade hook: mark existing courier request lines, sale lines and stock moves
    as hidden if they reference configured courier products.
    This runs once on module upgrade/install and is safe to re-run (idempotent).
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        courier_companies = env['codeware.courier.company'].search([])
        if not courier_companies:
            _logger.info("post_init_hook: no courier companies found.")
            return

        for cc in courier_companies:
            cp = cc.courier_product_id
            if not cp:
                continue
            prod_id = cp.id
            # mark request lines
            try:
                env['codeware.request.line'].search([('product_id', '=', prod_id)]).sudo().write({'is_courier_hidden': True})
                _logger.info("post_init_hook: marked request.line for product %s hidden", prod_id)
            except Exception as e:
                _logger.exception("post_init_hook: failed writing request lines for product %s: %s", prod_id, e)

            # mark sale order lines
            try:
                env['sale.order.line'].search([('product_id', '=', prod_id)]).sudo().write({'is_courier_hidden': True})
                _logger.info("post_init_hook: marked sale.order.line for product %s hidden", prod_id)
            except Exception as e:
                _logger.exception("post_init_hook: failed writing sale lines for product %s: %s", prod_id, e)

            # mark stock moves (so move_ids domain hides them)
            try:
                env['stock.move'].search([('product_id', '=', prod_id)]).sudo().write({'is_courier_hidden': True})
                _logger.info("post_init_hook: marked stock.move for product %s hidden", prod_id)
            except Exception as e:
                _logger.exception("post_init_hook: failed writing stock moves for product %s: %s", prod_id, e)

    except Exception as e_outer:
        _logger.exception("post_init_hook: unexpected error: %s", e_outer)
