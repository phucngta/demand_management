'''
Created on Dec 15, 2015

@author: Nguyen Phuc
'''
from openerp import models, fields, api

class forecast(models.Model):
    _name = 'demand.forecast'
    _description = 'Forecast Projects Management'

    name = fields.Char('Forecast Name', required=True)
    term_id= fields.Many2one('demand.term', string='Term', store=True, related="period_id.term_id", required=True)
    period_id = fields.Many2one('demand.period', string='Period', required=True)

    product_id = fields.Many2one('product.product',string="Product")
    product_uom = fields.Many2one('product.uom', string='Unit of Measure')
    history_ids = fields.One2many('demand.history', 'forecast_id', string='Sale History')

    forecast_method = fields.Selection([('sma','Simple Moving Average'),('es','Exponential Smoothing'),('lte','Linear Trend Equation')], "Method" ,default='sma')
    forecast_quantity = fields.Float(string='Forecast Quantity')
    mad = fields.Float(string='MAD')
    mape = fields.Float(string='MAPE')
    track_signal = fields.Float(string='Tracking Signal')

    state = fields.Selection([
        ('draft', "Draft"),
        ('open', "Open"),
        ('done', "Done"),
    ], 'Status', default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_open(self):
        self.state = 'open'

    @api.multi
    def action_done(self):
        self.state = 'done'

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
       
class history (models.Model):
    _name = 'demand.history'
    _description = 'Forecast History Management'

    forecast_id = fields.Many2one('demand.forecast', string='Forecast')

    term_id = fields.Many2one('demand.term', string='Term', store=True, related="forecast_id.term_id", readonly=True)
    period_id= fields.Many2one('demand.period', string='Period', store=True, domain = "[('period_id.id','in','term_id.period_ids.mapped('id')')]", required=True)
    total_sales = fields.Float('Total Sales', readonly=True)

    state = fields.Selection([('draft','Open'), ('done','Closed')], 'Status', readonly=True, copy=False, default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_done(self):
        self.state = 'done'

    @api.onchange('term_id')
    def onchange_term_id(self):
        res = {}
        if self.term_id:
            ids = self.term_id.period_ids.mapped('id')
            res['domain'] = {
            'period_id': [('id', 'in', ids)]
            }   
        return res