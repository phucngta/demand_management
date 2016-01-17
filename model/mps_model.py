# -*- coding: utf-8 -*-
from openerp import models, fields, api

class mps(models.Model):
    _name = 'demand.mps'

    name = fields.Char('Planning Name', required=True)

    forecast_lines = fields.Many2one('demand.forecast.line', string = 'Forecast Line', domain=[('state','=','draft')], readonly=True, states={'draft': [('readonly',False)]} )
    forecast_quantity = fields.Float('Forecasting quantity', readonly=True)

    term_id= fields.Many2one('demand.term', string='Term', readonly=True, related="forecast_lines.term_id")
    period_id = fields.Many2one('demand.period', string='Period', readonly=True, related="forecast_lines.period_id")

    product_id = fields.Many2one('product.product',string="Product", readonly=True, related="forecast_lines.forecast_id.product_id")
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', readonly=True, related="forecast_lines.forecast_id.product_uom")

    qty_available = fields.Float('Stock On Hand', readonly=True)
    virtual_available = fields.Float('Stock Accounting', readonly=True)
    incoming_qty = fields.Float('Incoming Quantity', readonly=True)
    outgoing_qty = fields.Float('Outging Quantity', readonly=True)

    product_min_qty = fields.Float('Minimum Quantity', readonly=True)
    product_max_qty = fields.Float('Maximum Quantity', readonly=True)

    consult_quantity = fields.Float('Consultant Quantity', readonly=True)
    plan_quantity = fields.Float('Procurement Quantity', required=True, readonly=True, states={'draft': [('readonly',False)]})
    
    
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

    @api.multi
    @api.depends('product_id')
    def calculate_plan(self):
        if self.product_id:
            for op in self.product_id.orderpoint_ids:
                self.product_min_qty = op.product_min_qty
                self.product_max_qty = op.product_max_qty

            self.forecast_quantity = self.forecast_lines.forecast

            self.qty_available = self.product_id.qty_available
            self.virtual_available = self.product_id.virtual_available
            self.incoming_qty = self.product_id.incoming_qty
            self.outgoing_qty = self.product_id.outgoing_qty

            consult_quantity = self.forecast_quantity - self.virtual_available + self.product_min_qty
            if consult_quantity > 0
                self.consult_quantity = consult_quantity

    @api.multi
    def request_procurement(self):
        self.ensure_one()
        value_dict = {'product_id': self.product_id.id,
                      'uom_id': self.product_id.uom_id.id,
                      'date_planned': self.period_id.date_start,
                      'qty': self.plan_quantity,
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