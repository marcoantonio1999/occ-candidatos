import tempfile
import unittest
import zipfile
import sys
from types import SimpleNamespace
from unittest.mock import patch
from computrabajo import profile_id, offer_id, extract, merge_rows
from occ_app import Progress
from occ_prueba import export_xlsx
from computrabajo import collect, DISCOVER

BASE = 'https://empresa.mx.computrabajo.com/Company/MatchCvDetail/MatchDetail?oi='+'A'*32+'&ims='

class ComputrabajoTests(unittest.TestCase):
    def test_full_collection_pages_and_recovery_after_interruption(self):
        offer='A'*32
        listing='https://empresa.mx.computrabajo.com/Company/Offers/Match?oi='+offer+'&cf=received'
        discarded=listing.replace('received','discarded')
        profiles=[dict(url=BASE+c*32,name='Persona '+c,review_state='No identificado') for c in 'BCD']
        class Driver:
            current_url=listing
            page=0
            opened=[]
            fail=True
            def get(self,url):
                self.current_url=listing if url=='https://empresa.mx.computrabajo.com/Company' else url
                self.page=0
                if profile_id(url):
                    self.opened.append(url)
                    if self.fail and url==profiles[1]['url']: raise OSError('Disconnected')
            def set_page_load_timeout(self,n): pass
            def quit(self): pass
            def execute_script(self,script):
                if script==DISCOVER:
                    return [profiles[2]] if self.current_url==discarded else [profiles[self.page]]
                return [listing,discarded]
            def find_elements(self,by,selector):
                if self.current_url==discarded or self.page==1:return []
                def click():self.page=1
                return [SimpleNamespace(is_displayed=lambda:True,is_enabled=lambda:True,get_attribute=lambda n:'',click=click)]
            def find_element(self,by,tag):
                name=next(x['name'] for x in profiles if x['url']==self.current_url)
                return SimpleNamespace(text='Currículum de '+name+'\nExperiencia profesional\nTrabajo ficticio\nFormación\nEscuela ficticia\nIdiomas\nEspañol')
        class Wait:
            def __init__(self,driver,n):self.driver=driver
            def until(self,fn):
                result=fn(self.driver)
                if not result:raise TimeoutError()
                return result
        driver=Driver()
        modules={'selenium':SimpleNamespace(webdriver=SimpleNamespace(Chrome=lambda **kw:driver,ChromeOptions=lambda:SimpleNamespace(add_argument=lambda x:None))),
                 'selenium.webdriver.common.by':SimpleNamespace(By=SimpleNamespace(CSS_SELECTOR='css',TAG_NAME='tag')),
                 'selenium.webdriver.support.ui':SimpleNamespace(WebDriverWait=Wait)}
        with tempfile.TemporaryDirectory() as folder,patch.dict(sys.modules,modules):
            p=Progress(folder)
            p.data=dict(version=1,platform='computrabajo',action='new',vacancy='Auxiliar',mode='all',candidates=[],selected=[],rows=[],done=[],pages=0,listed=False,complete=False,skipped=0)
            p.ready.set();collect(p)
            self.assertEqual(len(p.data['selected']),3)
            self.assertEqual(p.data['done'],[profiles[0]['url']])
            self.assertFalse(p.data['complete'])
            restarted=Progress(folder);restarted.ready.set();driver.fail=False;driver.opened=[]
            collect(restarted)
            self.assertTrue(restarted.data['complete'])
            self.assertNotIn(profiles[0]['url'],driver.opened)
            self.assertEqual(len(restarted.data['rows']),3)
            self.assertTrue(restarted.excel().exists())

    def test_validated_links(self):
        self.assertTrue(profile_id(BASE+'B'*32))
        self.assertFalse(profile_id((BASE+'B'*32).replace('.com/', '.com.evil/')))
        self.assertFalse(profile_id(BASE+'invalid'))
        self.assertFalse(offer_id(BASE+'B'*32))

    def test_sections_and_contact(self):
        row = extract('Currículum de Persona de Prueba\n52-5512345678\nExperiencia profesional\nAnalista\nEmpresa ficticia\nFormación\nUniversidad ficticia\nConocimientos y habilidades\nOtros\nExcel\nIdiomas\nInglés (Básico)\nGestiona el CV de Persona de Prueba\nContactar', 'Persona de Prueba')
        self.assertEqual(row['phone'],'5512345678')
        self.assertIn('Analista',row['experience'])
        self.assertEqual(row['languages'],'Inglés (Básico)')
        with self.assertRaises(ValueError): extract('Currículum de Otra persona','Persona de Prueba')

    def test_update_keeps_old_and_separates_homonyms(self):
        a=dict(url=BASE+'B'*32,name='Persona',phone='5512345678',education='Escuela anterior')
        b=dict(url=BASE+'C'*32,name='Persona',phone='',education='Otra escuela')
        rows=merge_rows([a],[{**a,'education':'Escuela nueva'},b])
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['education'],'Escuela nueva')
        self.assertEqual(merge_rows(rows,[{**a,'education':''}])[0]['education'],'Escuela nueva')
        with tempfile.TemporaryDirectory() as folder:
            path=__import__('pathlib').Path(folder)/'result.xlsx'
            export_xlsx(rows,path,deduplicate=False)
            with zipfile.ZipFile(path) as z:
                self.assertEqual(z.read('xl/worksheets/sheet1.xml').count(b'<row '),3)

    def test_previous_vacancy_is_bound_to_portal_offer_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Progress(folder)
            with patch('occ_app.threading.Thread'):
                p.begin('Auxiliar','all',consent=True,platform='computrabajo')
                p.data.update(complete=True,offer_id='A'*32,rows=[dict(url=BASE+'B'*32,name='Persona',phone='')])
                p.save();p.busy=False
                p.begin('Auxiliar','all',consent=True,platform='computrabajo',action='update')
            self.assertEqual(len(p.previous_rows('computrabajo','Auxiliar','A'*32)),1)
            self.assertEqual(p.previous_rows('computrabajo','Auxiliar','D'*32),[])
            resumed=Progress(folder)
            self.assertEqual(resumed.data['action'],'update')
            self.assertEqual(resumed.data['platform'],'computrabajo')

if __name__=='__main__': unittest.main()
