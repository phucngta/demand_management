'''
Created on Dec 15, 2015

@author: Nguyen Phuc
'''
from datetime import datetime
from openerp import models, fields, api

class forecast(models.Model):
    _name = 'demand.forecast'
    _description = 'Forecast Projects Management'

    name = fields.Char('Forecast Name', required=True)
    term_id= fields.Many2one('demand.term', string='Term', store=True, required=True)
    period_id = fields.Many2one('demand.period', string='Period', required=True)

    product_id = fields.Many2one('product.product',string="Product", required=True)
    product_uom = fields.Many2one('product.uom', string='Unit of Measure')
    history_ids = fields.One2many('demand.history', 'forecast_id', string='Sale History')

    forecast_method = fields.Selection([('sma','Simple Moving Average'),('es','Exponential Smoothing')], "Method" ,default='sma')
    interval = fields.Integer('Interval', required = True)
    alpha = fields.Float('Alpha', required = True)
    
    sum_error = fields.Float(string='Sum error')
    avg_demand = fields.Float(string='Average Demand')

    mad = fields.Float(string='MAD')
    mape = fields.Float(string='MAPE')
    track_signal = fields.Float(string='Tracking Signal')
    forecast_quantity = fields.Float(string='Forecast Quantity')

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
        self.period_id = None
        res = {}
        if self.term_id:
            ids = self.term_id.period_ids.mapped('id')
            res['domain'] = {
            'period_id': [('id', 'in', ids)]
            }   
        return res
    
    @api.multi
    @api.depends('product_id')
    def _sale_per_product(self, pe):
        so_obj = self.env['sale.order']
        sol_obj = self.env['sale.order.line']
        self.avg_demand = 0

        # Kiem tra cac don hang ve san pham co ton tai
        sol_with_product = sol_obj.search([('product_id','=',self.product_id.id), ('order_id.date_order','>=', pe.date_start), ('order_id.date_order','<=', pe.date_end)])
        if sol_with_product:
            # Kiem tra ngay sale order nam trong period
            # so_in_period = so_obj.search([('date_order','>=',pe.date_start),('date_order','<=',pe.date_end)])
            # if so_in_period:
            #     # sql = '''SELECT sum(sol.product_uom_qty) 
            #     #     FROM sale_order_line AS sol LEFT JOIN sale_order AS so ON (so.id = sol.order_id)
            #     #     WHERE (sol.id IN %s) AND (so.id IN %s) AND (so.state NOT IN (\'draft\',\'cancel\'))'''
            #     sql = '''SELECT sum(sol.product_uom_qty) 
            #         FROM sale_order_line AS sol LEFT JOIN sale_order AS so ON (so.id = sol.order_id)
            #         WHERE (sol.product_id = %s) AND (so.date_order >= %s) AND (so.date_order <= %s) AND (so.state NOT IN (\'draft\',\'cancel\'))''' % (self.product_id.id, datetime.strptime(pe.date_start, '%Y-%m-%d'), datetime.strptime(pe.date_end, '%Y-%m-%d'))
            #     self.env.cr.execute(sql)
            #     return self.env.cr.fetchone()
            # return 11
            sum_quantity = 0
            n = 0
            for sol in sol_with_product:
                n += 1
                sum_quantity += sol.product_uom_qty
            self.avg_demand = sum_quantity/n
            return sum_quantity

    @api.one
    @api.depends('period_id','term_id','product_id')
    def create_history(self):
        # Xoa history cu
        self.history_ids.unlink()

        # Tao lich su
        history_obj = self.env['demand.history']
        ds = datetime.strptime(self.period_id.date_start, '%Y-%m-%d')
        for pe in self.term_id.period_ids:
            if pe.date_end < ds.strftime('%Y-%m-%d'):
                history_obj.create({
                    'period_id' : pe.id,
                    'term_id' : self.term_id.id,
                    'forecast_id' : self.id,
                    'demand' : self._sale_per_product(pe),
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