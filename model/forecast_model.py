'''
Created on Dec 15, 2015

@author: Nguyen Phuc
'''
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import models, fields, api, exceptions

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

    @api.one
    @api.depends('period_id','term_id')
    def create_history(self):
        # Xoa history cu
        self.history_ids.unlink()

        # Tao history moi
        history_obj = self.env['demand.history']
        ds = datetime.strptime(self.period_id.date_start, '%Y-%m-%d')
        for pe in self.term_id.period_ids:
            if pe.date_end < ds.strftime('%Y-%m-%d'):
                history_obj.create({
                    'period_id' : pe.id,
                    'term_id' : self.term_id.id,
                    'forecast_id' : self.id,
                })
       
class history (models.Model):
    _name = 'demand.history'
    _description = 'Forecast History Management'

    @api.one
    @api.depends('demand', 'forecast')
    def _get_error(self):
        self.error = self.demand - self.forecast
        self.absolute_error = abs(self.demand - self.forecast)

    forecast_id = fields.Many2one('demand.forecast', string='Source', readonly=True)

    term_id = fields.Many2one('demand.term', string='Term', store=True, related="forecast_id.term_id", readonly=True)
    period_id= fields.Many2one('demand.period', string='Period', store=True, domain = "[('period_id.id','in','term_id.period_ids.mapped('id')')]", required=True)

    demand = fields.Float('Demand')
    forecast = fields.Float('Forecast')
    error = fields.Float('Error', readonly=True, compute='_get_error', store=True)
    absolute_error = fields.Float('Absolute Error', readonly=True, compute='_get_error', store=True)

    state = fields.Selection([('draft','Open'), ('done','Closed')], 'Status', readonly=True, default='draft')

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