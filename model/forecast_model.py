'''
Created on Dec 15, 2015

@author: Nguyen Phuc
'''
from datetime import datetime
from openerp import models, fields, api, exceptions

class forecast(models.Model):
    _name = 'demand.forecast'

    @api.one
    @api.depends('forecast_lines')
    def _count_forecast_lines(self):
        forecast_line_lst = []
        sum_demand = 0
        for line in self.forecast_lines:
            if line.id:
                forecast_line_lst.append(line.id)
                sum_demand += line.demand_qty
        
        forecast_line_count = len(forecast_line_lst)
        if forecast_line_count > 0:
            self.avg_demand = sum_demand /forecast_line_count

    name = fields.Char('Forecast Name', required=True)
    term_id= fields.Many2one('demand.term', string='Term', required=True, readonly=True, states={'draft': [('readonly',False)]}, domain=[('state','=','draft')])
    period_id = fields.Many2one('demand.period', string=' End Period', required=True, readonly=True, states={'draft': [('readonly',False)]}, domain=[('state','=','draft')])

    product_id = fields.Many2one('product.product',string="Product", required=True, readonly=True, states={'draft': [('readonly',False)]})
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True, readonly=True, states={'draft': [('readonly',False)]})
    forecast_lines = fields.One2many('demand.forecast.line', 'forecast_id', string='Forecast Line',readonly=True, states={'draft': [('readonly',False)]})

    forecast_method = fields.Selection([('sma','Simple Moving Average'),('es','Exponential Smoothing')], "Method" ,default='sma', readonly=True, states={'draft': [('readonly',False)]})
    interval = fields.Integer('Interval', required = True, default=2, readonly=True, states={'draft': [('readonly',False)]})
    alpha = fields.Float('Alpha', required = True, default=0.5, readonly=True, states={'draft': [('readonly',False)]})
    
    avg_demand = fields.Float(string='Average Demand', readonly=True, compute=_count_forecast_lines, store=True)

    mad = fields.Float(string='MAD', readonly=True)
    mape = fields.Float(string='MAPE', readonly=True)
    track_signal = fields.Float(string='Tracking Signal', readonly=True)

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
        for line in self.forecast_lines:
            line.state = 'done'

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id

    @api.onchange('forecast_method')
    def onchange_forecast_method(self):
        if self.forecast_method:
            self.mad = self.mape = self.track_signal = 0

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

    @api.one
    @api.depends('alpha')
    def _forecast_by_exponentail_smoothing(self, alpha):
        # Lay so phan tu forecast line
        forecast_line_obj = self.env['demand.forecast.line']
        ids = self.forecast_lines.mapped('id')
        number_lines = len(ids)

        # Kiem tra alpha
        if (alpha <= 0) | (alpha >= 1):
            raise exceptions.ValidationError("Alpha phai nam trong khoang (0 .. 1)")

        # Gan forecast dau tien
        first_forecast_line = forecast_line_obj.browse([ids[0]])
        forecast_value = first_forecast_line.demand_qty
        first_forecast_line.write({'forecast_qty': forecast_value})

        # Tinh forecast trong tung sale history
        sum_error = sum_ab_error = error = 0
        i = 1
        while i < number_lines :
            forecast_value = forecast_value + alpha*error

            forecast_line = forecast_line_obj.browse([ids[i]])
            forecast_line.write({'forecast_qty': forecast_value})

            error = forecast_line.demand_qty - forecast_value
            sum_error += error
            sum_ab_error += abs(error)
            i += 1

        # Tinh do sai lech
        self.mad = sum_ab_error/number_lines
        self.mape = self.mad/self.avg_demand
        self.track_signal = sum_error/self.mad

    @api.one
    @api.depends('interval')
    def _forecast_by_simple_moving_average(self, interval):
        # Lay so phan tu lich su
        forecast_line_obj = self.env['demand.forecast.line']
        ids = self.forecast_lines.mapped('id')
        number_lines = len(ids)
        
        # Kiem tra interval co lon hon so luong lich su
        if number_lines < interval:
            raise exceptions.ValidationError("Interval phai nho hon so luong period")

        # Tinh gia tri forecast
        sum_error = sum_ab_error = error = 0
        i = 0
        while  i < number_lines:
            # Gan forecast dau tien
            if i < interval:
                forecast_line_obj.browse([ids[i]]).write({'forecast_qty': 0})

            else:
                count_down = interval
                sum_demand_interval = 0
                index = i - 1

                while count_down > 0:
                    sum_demand_interval += forecast_line_obj.browse([ids[index]]).demand_qty
                    index -= 1
                    count_down -= 1

                forecast_value = sum_demand_interval/interval
                forecast_line_obj.browse([ids[i]]).write({'forecast_qty': forecast_value})

                error = forecast_line_obj.browse([ids[i]]).demand_qty - forecast_value
                sum_error += error
                sum_ab_error += abs(error)

            i += 1

        # Tinh sai lech
        self.mad = sum_ab_error/(number_lines - interval)
        self.mape = self.mad/self.avg_demand
        self.track_signal = sum_error/self.mad

    @api.multi
    @api.depends('forecast_method','interval', 'alpha')
    def run_forecast(self):
        if self.forecast_method == 'es':
            self._forecast_by_exponentail_smoothing(self.alpha)
        elif  self.forecast_method == 'sma':
            self._forecast_by_simple_moving_average(self.interval)

    @api.multi
    @api.depends('product_id')
    def _sale_per_product(self, pe):
        # so_obj = self.env['sale.order']
        sol_obj = self.env['sale.order.line']

        # Kiem tra cac don hang ve san pham co ton tai
        sol_with_product = sol_obj.search([('product_id','=',self.product_id.id), ('order_id.date_order','>=', pe.date_start), ('order_id.date_order','<=', pe.date_end)])
        if sol_with_product:
            sum_quantity = 0
            for sol in sol_with_product:
                sum_quantity += sol.product_uom_qty
            return sum_quantity

    @api.one
    @api.depends('period_id','term_id','product_id')
    def create_forecast_lines(self):
        # Xoa forecast line cu
        self.forecast_lines.unlink()

        # Tao Temporate Demand
        forecast_obj = self.env['demand.forecast']
        if forecast_obj.search([('name','=','Actual: '+self.name)]).exists():
            tmp_demand = forecast_obj.search([('name','=','Actual: '+self.name)])
            tmp_demand.forecast_lines.unlink()
        else: 
            tmp_demand = forecast_obj.create({
                'name' : 'Actual: '+self.name,
                'term_id' : self.term_id.id,
                'period_id' : self.period_id.id,
                'product_id' : self.product_id.id,
                'product_uom' : self.product_uom.id,
                'state' : 'done',
            })

        # Tao forecast line 
        forecast_line_obj = self.env['demand.forecast.line']
        de = datetime.strptime(self.period_id.date_end, '%Y-%m-%d')
        for pe in self.term_id.period_ids:
            if pe.date_end <= de.strftime('%Y-%m-%d'):
                forecast_line_obj.create({
                    'name' : 'Forecast '+pe.name,
                    'period_id' : pe.id,
                    'term_id' : self.term_id.id,
                    'forecast_id' : self.id,
                    'demand_qty' : self._sale_per_product(pe),
                })
                forecast_line_obj.create({
                    'name' : 'Demand '+pe.name,
                    'period_id' : pe.id,
                    'term_id' : self.term_id.id,
                    'forecast_id' : tmp_demand.id,
                    'forecast_qty' : self._sale_per_product(pe),
                    'state' : 'done',
                })

    @api.multi
    def show_graph_forecast(self):
        forecast_line_lst = []

        forecast_obj = self.env['demand.forecast']
        tmp_demand = forecast_obj.search([('name','=','Actual: '+self.name)])
        if tmp_demand:
            for line in tmp_demand.forecast_lines:
                if line.id:
                    forecast_line_lst.append(line.id)

        for line in self.forecast_lines:
            if line.id:
                forecast_line_lst.append(line.id)

        return {
            'view_mode': 'graph',
            'res_model': 'demand.forecast.line',
            'res_ids': forecast_line_lst,
            'domain': [('id', 'in', forecast_line_lst)],
            'type': 'ir.actions.act_window',
            'target': 'new',
            }

    @api.multi
    def make_plan(self):
        self.ensure_one()

        plan_obj = self.env['demand.planning']
        if plan_obj.search([('forecast_id','=', self.id)]).exists():
            res_id = plan_obj.search([('forecast_id','=', self.id)])
        else:
            value_dict = {
                        'name' : 'Plan '+self.term_id.name,
                        'forecast_id': self.id,
                        'product_id': self.product_id.id,
                        'product_uom': self.product_uom.id,
                        'term_id': self.term_id.id,
                        }
            res_id = plan_obj.create(value_dict)

        for line in self.forecast_lines:
            line.planning_id = res_id.id

        return {
                'view_mode': 'form',
                'res_model': 'demand.planning',
                'res_id': res_id.id,
                'view_id': False,
                'type': 'ir.actions.act_window',
                }

class ForecastLine (models.Model):
    _name = 'demand.forecast.line'

    name = fields.Char('Forecast Line Name', required=True)
    forecast_id = fields.Many2one('demand.forecast', string='Source', readonly=True, required=True)
    planning_id = fields.Many2one('demand.planning', string='Source Plan', readonly=True)
    planning_line_id = fields.Many2one('demand.planning.line', string='Plan', readonly=True)

    term_id = fields.Many2one('demand.term', string='Term', required=True, readonly=True)
    period_id= fields.Many2one('demand.period', string='Period', required=True, readonly=True)
    # domain = "[('period_id.id','in','term_id.period_ids.mapped('id')')]", 

    demand_qty = fields.Float('Demand Quantity', readonly=True)
    forecast_qty = fields.Float('Forecast Quantity', readonly=True)

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

    @api.multi
    def plan_production(self):
        self.ensure_one()
        plan_line_obj = self.env['demand.planning.line']

        if not self.planning_line_id.exists():
            res_id = plan_line_obj.create({
                        'name' : 'Plan '+self.period_id.name,
                        'forecast_line_id': self.id,
                        'demand_qty': self.demand_qty,
                        'forecast_qty': self.forecast_qty,
                        'term_id': self.term_id.id,
                        'period_id': self.period_id.id,
                        'planning_id':self.planning_id.id,
                        'qty_available': self.planning_id.qty_available,
                        'virtual_available': self.planning_id.virtual_available,
                        'incoming_qty': self.planning_id.incoming_qty,
                        'outgoing_qty': self.planning_id.outgoing_qty,
                        'product_min_qty': self.planning_id.product_min_qty,
                        'product_max_qty': self.planning_id.product_max_qty,
                        })
            self.planning_line_id = res_id.id
            self.state = 'open'
        
            return {
                'view_mode': 'form',
                'res_model': 'demand.planning',
                'res_id': self.planning_id.id,
                'view_id': False,
                'type': 'ir.actions.act_window',
                }