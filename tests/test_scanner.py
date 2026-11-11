import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import scanner as s


class RadarTests(unittest.TestCase):
    def test_job_title_matching(self):
        self.assertIsNotNone(s.match_title('Financial Accountant'))
        self.assertIsNotNone(s.match_title('General Ledger Specialist'))
        self.assertIsNotNone(s.match_title('Business Controller'))
        self.assertIsNotNone(s.match_title('Contabile Generale'))
        self.assertIsNotNone(s.match_title('Addetto Ciclo Passivo'))
        self.assertIsNone(s.match_title('Account Manager'))
        self.assertIsNone(s.match_title('Account Executive'))
        self.assertIsNone(s.match_title('Software Developer'))
        self.assertGreater(s.match_title('Financial Accountant','SAP, month-end closing and intercompany reconciliation')['score'],69)

    def test_location_rules(self):
        self.assertEqual(s.geography('Milan, Italy'),['lombardy'])
        self.assertEqual(s.geography('Biassono, Italy'),['lombardy'])
        self.assertEqual(s.geography('Rome, Italy'),['rest'])
        self.assertEqual(s.geography('Milan / Rome'),['lombardy','rest'])
        self.assertEqual(s.geography('Remote – Italy'),['verify'])
        self.assertEqual(s.geography('Remote – Europe'),[])
        self.assertEqual(s.geography('London, UK','GB'),[])
        self.assertEqual(s.geography('Anywhere', 'IT'),['verify'])

    def test_ashby_parser_and_job_conversion(self):
        company = {'id':'satispay', 'name':'Satispay','industry':'Fintech','provider':'ashby','token':'satispay'}
        def fake(_url):
            return {'jobs':[{'title':'Financial Accountant', 'location':'Milan, Italy','isListed':True,
                             'publishedAt':'2026-11-11T09:00:00Z', 'jobUrl':'https://jobs.ashbyhq.com/satispay/job1',
                             'descriptionPlain':'SAP Excel month-end closing'},
                            {'title':'Product Designer','location':'Milan, Italy','jobUrl':'https://jobs.ashbyhq.com/satispay/job2'}]}
        jobs = [s.job_from_raw(company, raw) for raw in s.source_jobs(company,fake)]
        self.assertEqual(sum(bool(j) for j in jobs),1)
        self.assertEqual(jobs[0]['published_at'],'2026-11-11T09:00:00Z')
        self.assertEqual(jobs[0]['geographies'],['lombardy'])

    def test_lever_parser(self):
        company = {'id':'ion', 'name':'ION Group','industry':'Fintech','provider':'lever','token':'ion'}
        jobs=list(s.source_jobs(company,lambda _:[{'id':'a','text':'GL Accountant','categories':{'location':'Milan','team':'Finance'},
               'hostedUrl':'https://jobs.lever.co/ion/a','createdAt':12345}]))
        self.assertEqual(jobs[0]['location'],'Milan')
        self.assertIsNone(jobs[0]['published_at'])  # creation != publication

    def test_greenhouse_parser(self):
        company = {'provider':'greenhouse','token':'truelayer'}
        jobs=list(s.source_jobs(company,lambda _:{'jobs':[{'id':5,'title':'Finance Assistant',
             'location':{'name':'Milan, Italy'},'absolute_url':'https://job-boards.greenhouse.io/truelayer/jobs/5',
             'updated_at':'2026-11-11T09:00:00Z','content':'<p>Excel &amp; SAP</p>'}]}))
        self.assertEqual(len(jobs),1)
        self.assertIn('Excel & SAP',jobs[0]['description'])
        self.assertIsNone(jobs[0]['published_at'])

    def test_first_baseline_silent_then_notifies_only_new(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            config=root/'companies.json'; state=root/'state.json'; data=root/'data.json'; outbox=root/'outbox.json'
            company={'id':'satispay','name':'Satispay','industry':'Fintech','mode':'api','provider':'ashby',
                     'token':'satispay','careers_url':'https://jobs.ashbyhq.com/satispay'}
            config.write_text(json.dumps({'companies':[company]}))
            seen=[{'title':'Accountant','location':'Milan, Italy','jobUrl':'https://jobs.ashbyhq.com/satispay/1'}]
            def fetch(_):return {'jobs':list(seen)}
            with patch.object(s,'CONFIG',config),patch.object(s,'STATE',state),patch.object(s,'SITE_DATA',data),patch.object(s,'OUTBOX',outbox),patch.object(s.time,'sleep',lambda *_:None):
                first, batch=s.monitor(fetcher=fetch,timestamp='2026-11-11T10:00:00Z')
                self.assertEqual(first['stats']['active_matches'],1)
                self.assertEqual(batch['priority'],[])
                seen.append({'title':'Business Controller','location':'Bergamo','jobUrl':'https://jobs.ashbyhq.com/satispay/2',
                             'descriptionPlain':'SAP, budget and forecasting'})
                second, batch=s.monitor(fetcher=fetch,timestamp='2026-11-11T11:00:00Z')
                self.assertEqual(second['stats']['new_this_scan'],1)
                self.assertEqual(len(batch['priority']),1)
                self.assertIn('Controller',batch['priority'][0]['title'])
                third, batch=s.monitor(fetcher=fetch,timestamp='2026-11-11T12:00:00Z')
                self.assertEqual(third['stats']['new_this_scan'],0)
                self.assertEqual(batch['priority'],[])

    def test_errors_do_not_claim_zero_open_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'config.json'
            c={'id':'truelayer','name':'TrueLayer','industry':'Fintech','mode':'api','provider':'greenhouse','token':'truelayer','careers_url':'https://job-boards.greenhouse.io/truelayer'}
            config.write_text(json.dumps({'companies':[c]}))
            with patch.object(s,'CONFIG',config),patch.object(s,'STATE',root/'state.json'),patch.object(s,'SITE_DATA',root/'data.json'),patch.object(s,'OUTBOX',root/'outbox.json'),patch.object(s.time,'sleep',lambda *_:None):
                first,_=s.monitor(lambda _:{'jobs':[{'id':2,'title':'Financial Accountant','location':{'name':'Milan, Italy'},'absolute_url':'https://example.org/job'}]},timestamp='2026-11-11T10:00:00Z')
                self.assertEqual(first['stats']['active_matches'],1)
                def broken(_):raise RuntimeError('timeout')
                second,_=s.monitor(broken,timestamp='2026-11-11T11:00:00Z')
                self.assertEqual(second['stats']['active_matches'],1)
                self.assertTrue(second['jobs'][0]['stale'])
                self.assertEqual(second['companies'][0]['status'],'error')

if __name__=='__main__':unittest.main()
