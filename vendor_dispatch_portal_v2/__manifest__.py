# -*- coding: utf-8 -*-
{
    'name': 'Vendor Dispatch Portal',
    'version': '1.0.0',
    'summary': 'Vendor portal to submit dispatch details for dropship orders; customers can view them.',
    'category': 'Warehouse',
    'author': 'Prime Minds Services for User',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'portal',
        'contacts',
        'stock',
        'delivery',
        'sale_management',
        'website',
'stock_dropshipping','sale',
    ],

    'assets': {

    'web.assets_frontend': [
        'vendor_dispatch_portal_v2/static/src/css/customer_tracking.css',
    ],
    },

    'data': ['security/security_rules.xml',
        'security/ir.model.access.csv',
         "views/product_template_view.xml",
        'views/dispatch_views.xml',
        'views/dispatch_templates.xml',
        'views/email_templates.xml',
    ],


    'installable': True,
    'application': False,
'auto_install': False,
}
