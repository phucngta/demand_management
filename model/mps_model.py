# -*- coding: utf-8 -*-
from openerp import models, fields, api

class mps(models.Model):
    _name = 'demand.mps'

    name = fields.Char('Schedule Name', required=True)

    forecast_id = fields.Many2one('demand.forecast', string = 'Forecast name', domain=[('state','=','open')], readonly=True, states={'draft': [('readonly',False)]} )
    forecast_quantity = fields.Float('Forecasting quantity', readonly=True, states={'draft': [('readonly',False)]})

    term_id= fields.Many2one('demand.term', string='Term', required=True, readonly=True, states={'draft': [('readonly',False)]})
    period_id = fields.Many2one('demand.period', string='Period', required=True, readonly=True, states={'draft': [('readonly',False)]})

    product_id = fields.Many2one('product.product',string="Product", required=True, readonly=True, states={'draft': [('readonly',False)]})
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True, readonly=True, states={'draft': [('readonly',False)]})

    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse", required=True, readonly=True, states={'draft': [('readonly',False)]})
    qty_available = fields.Float('Quantity On Hand', readonly=True)
    incoming_shipment = fields.Float('Incoming Shipment', readonly=True)

    consult_quantity = fields.Char('Consultant Quantity', readonly=True)
    plan_quantity = fields.Float('Planed Quantity', required=True, readonly=True, states={'draft': [('readonly',False)]})
    
    
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

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id
            

    @api.onchange('term_id')
    def onchange_term_id(self):
        res = {}
        if self.term_id:
            ids = self.term_id.period_ids.mapped('id')
            res['domain'] = {
            'period_id': [('id', 'in', ids)]
            }   
        return res

    @api.onchange('forecast_id')
    def _onchange_forecast(self):
        self.forecast_quantity = self.forecast_id.forecast_quantity
        self.term_id = self.forecast_id.term_id
        self.period_id = self.forecast_id.period_id
        self.product_id = self.forecast_id.product_id
        self.product_uom = self.forecast_id.product_uom

    @api.multi
    @api.depends('product_id')
    def get_stock(self, pe):
        self.stock_on_hand = self.product_id.qty_available
        
        # quant_obj = self.env['stock.quant']
        # quant_with_product = quant_obj.search([('product_id','=',self.product_id.id)])
        # if quant_with_product:
        #     sum_stock = 0
        #     for stock in quant_with_product:
        #         sum_stock += stock.qty
        #     self.stock_on_hand = sum_stock

    @api.multi
    def request_procurement(self):
        self.ensure_one()
        value_dict = {'product_id': self.product_id.id,
                      'uom_id': self.product_id.uom_id.id,
                      'date_planned': self.period_id.date_start,
                      'qty': self.plan_quantity,
                      'warehouse_id': self.warehouse_id.id
                      }
        res_id = self.env['make.procurement'].create(value_dict)
        return {'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'make.procurement',
                'res_id': res_id.id,
                'view_id': False,
                'type': 'ir.actions.act_window',
                'target': 'new',
                }


    # @api.multi    
    # def getdata(self):
    #     sql='''SELECT qty_available FROM product.product as pro WHERE self.MPS_product=pro.name'''
    #     self.env.cr.execute(sql)    
    #     self.MPS_stock = self.env.cr.fetchone()    