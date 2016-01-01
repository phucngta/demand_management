'''
Created on Dec 15, 2015

@author: Nguyen Phuc
'''
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import models, fields, api, exceptions

class Term(models.Model):
    _name = 'demand.term'
    _description = 'Demand term'

    @api.one
    @api.depends('period_ids')
    def _get_period_count(self):
        period_lst = []
        for line in self.period_ids:
            if line.id:
                period_lst.append(line.id)
        self.period_count = len(period_lst)

    name = fields.Char('Term Name', required=True)
    date_start= fields.Date('Start of Term', required=True, states={'done':[('readonly',True)]})
    date_end= fields.Date('End of Term', required=True, states={'done':[('readonly',True)]})

    num_cycle=fields.Integer('Number of Cycles', default='1', states={'done':[('readonly',True)]})
    type_period=fields.Selection([('day','day(s)'),('week','week(s)'),('month','month(s)')],default='day', states={'done':[('readonly',True)]})
    
    period_ids = fields.One2many('demand.period', 'term_id', string= 'Periods', states={'done':[('readonly',True)]})
    period_count = fields.Integer(string="Period Count", compute=_get_period_count)

    state = fields.Selection([('draft','Open'), ('done','Closed')], 'Status', readonly=True, copy=False, default='draft')
    

    @api.one
    @api.constrains('date_start', 'date_end')
    def check_dates(self):
        if self.date_start >= self.date_end:
            raise exceptions.ValidationError("Ngay bat dau phai nho hon ngay ket thuc")
            
    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_done(self):
        self.state = 'done'
    
    @api.one
    @api.depends('type_period','num_cycle')
    def create_period(self):
        # Xoa period cu
        self.period_ids.unlink()

        # Tao period moi
        period_obj = self.env['demand.period']        
        ds = datetime.strptime(self.date_start, '%Y-%m-%d')
        
        if self.type_period == 'month':
            while ds.strftime('%Y-%m-%d') < self.date_end:
                    de = ds + relativedelta(months = self.num_cycle, days=-1)
    
                    if de.strftime('%Y-%m-%d') > self.date_end:
                        de = datetime.strptime(self.date_end, '%Y-%m-%d')
    
                    period_obj.create({
                        'name': ds.strftime('%m/%Y'),
                        'date_start': ds.strftime('%Y-%m-%d'),
                        'date_end': de.strftime('%Y-%m-%d'),
                        'term_id': self.id,
                    })
                    ds = ds + relativedelta(months = self.num_cycle)
        
        elif self.type_period == 'week':
            while ds.strftime('%Y-%m-%d') < self.date_end:
                    de = ds + relativedelta(weeks = self.num_cycle, days=-1)
    
                    if de.strftime('%Y-%m-%d') > self.date_end:
                        de = datetime.strptime(self.date_end, '%Y-%m-%d')
    
                    period_obj.create({
                        'name': ds.strftime('Week %W %m/%Y'),
                        'date_start': ds.strftime('%Y-%m-%d'),
                        'date_end': de.strftime('%Y-%m-%d'),
                        'term_id': self.id,
                    })
                    ds = ds + relativedelta(weeks = self.num_cycle)
                    
        elif self.type_period == 'day':
            while ds.strftime('%Y-%m-%d') < self.date_end:
                    de = ds + relativedelta(days = self.num_cycle)
    
                    if de.strftime('%Y-%m-%d') > self.date_end:
                        de = datetime.strptime(self.date_end, '%Y-%m-%d')
    
                    period_obj.create({
                        'name': ds.strftime('Period %d')+de.strftime('-%d')+ds.strftime('/%m'),
                        'date_start': ds.strftime('%Y-%m-%d'),
                        'date_end': de.strftime('%Y-%m-%d'),
                        'term_id': self.id,
                    })
                    ds = ds + relativedelta(days = self.num_cycle+1)

    # @api.one
    # def delete_period(self):
    #     sql='''
    #         DELETE FROM demand_period
    #         WHERE term_id = '%s'
    #     '''%(self.id)
    #     self.env.cr.execute(sql)

    # @api.one
    # def delete_period(self):
    #     self.period_ids.unlink()
        

class Period(models.Model):
    _name = 'demand.period'
    _description = 'Demand period'
    _order = 'date_start, id' 
    name = fields.Char('Period Name', required=True)
    date_start= fields.Date('Start of Period', required=True, states={'done':[('readonly',True)]})
    date_end= fields.Date('End of Period', required=True, states={'done':[('readonly',True)]})

    term_id = fields.Many2one('demand.term', string='Term', required=True, states={'done':[('readonly',True)]}, select=True)

    state = fields.Selection([('draft','Open'), ('done','Closed')], 'Status', readonly=True, copy=False, default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_done(self):
        self.state = 'done'

    @api.one
    @api.constrains('date_start', 'date_end')
    def check_dates(self):
        if self.date_start > self.date_end:
            raise exceptions.ValidationError("Ngay bat dau phai nho hon ngay ket thuc")
           
    