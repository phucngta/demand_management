# -*- coding: utf-8 -*-
from openerp import models, fields, api

class MPS(models.Model):
    _name = 'mps.mps'
    MPS_name = fields.Char('Planning', required=True)

    # forecast_id = fields.Many2one('', string = 'Forecast name')
    forecast_quantity = fields.Float('Forecasting quantity')
#    period_id = fields.Char('Period')
#    term_id = fields.Char('Term')
    
    MPS_product = fields.Many2one('product.product',string="Product")
    MPS_stock = fields.Float('Stock on hand',  required=False)
    MPS_order = fields.Float('Sale order', required=False)
    MPS_incomeship = fields.Float('Incoming Shipment', required=False)
    
    MPS_quantity = fields.Float('Procurement Quantity', required=True)
    MPS_calquantity = fields.Char('Consultant Quantity', required=False)
    
    MPS_period = fields.Char('Period', required=True)
    state = fields.Selection([
            ('draft', "Draft"),
            ('open', "Open"),
            ('close', "Close"),
            ], default='draft')
    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_open(self):
        self.state = 'open'

    @api.multi
    def action_close(self):
        self.state = 'close'

    @api.multi    
    def getdata(self):
        sql='''SELECT qty_available FROM product.product as pro WHERE self.MPS_product=pro.name'''
        self.env.cr.execute(sql)    
        self.MPS_stock = self.env.cr.fetchone()    