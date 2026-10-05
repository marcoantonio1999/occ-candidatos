import unittest
from occ_prueba import seen_status, allowed_profile, unique, extract_profile, extract_sections, select_candidates

class SafetyTests(unittest.TestCase):
    def test_filter_modes(self):
        base = 'https://empresa.occ.com.mx/empresas/candidatos/1/cv/2/'
        items = [{'url':base+'3','complete_card':True,'labels':[]}, {'url':base+'4','complete_card':True,'labels':['Sin ver']}, {'url':base+'5','labels':[]}]
        self.assertEqual([r['review_state'] for r in select_candidates(items, 'seen')], ['Visto'])
        self.assertEqual([r['review_state'] for r in select_candidates(items, 'unseen')], ['Sin ver'])
        self.assertEqual(len(select_candidates(items, 'all')), 2)
        self.assertEqual(len(select_candidates(items, 'all', 1)), 1)
    def test_seen_only(self):
        self.assertTrue(seen_status(['Visto']))
        self.assertFalse(seen_status(['Sin ver']))
        self.assertFalse(seen_status([]))
        self.assertFalse(seen_status(['Visto', 'Sin ver']))
        self.assertFalse(seen_status(['Me interesa']))
        self.assertTrue(seen_status([], complete_card=True))
        self.assertFalse(seen_status(['Sin ver'], complete_card=True))
        self.assertFalse(seen_status(['No visto'], complete_card=True))
    def test_urls(self):
        self.assertTrue(allowed_profile('https://empresa.occ.com.mx/empresas/candidatos/40023555/cv/123/456'))
        self.assertFalse(allowed_profile('https://empresa.occ.com.mx.evil.test/empresas/candidatos/1/cv/2/3'))
    def test_profile(self):
        text = 'Persona de Prueba\nCuauhtémoc, Ciudad de México\n$8,000 MXN\nDatos de contacto\n5512345678\nmail@example.com\nDescarga CV\nCV: 12345678'
        self.assertEqual(extract_profile(text), {'name': 'Persona de Prueba', 'phone': '5512345678'})
        self.assertIsNone(extract_profile('Datos de contacto\nDescarga CV\nCV: 5549285070'))
    def test_duplicate(self):
        rows = [{'name':'Ana López','phone':'5512345678','vacancy':'A'}, {'name':' ana  lópez ','phone':'5587654321','vacancy':'B'}, {'name':'Luis','phone':'5512345678','vacancy':'C'}]
        self.assertEqual(len(unique(rows)), 1)
    def test_cv_sections(self):
        result = extract_sections('Información de tu vacante\nAuxiliar\nExperiencia laboral\nEjecutivo de calidad\nBanorre\n2025 | 2026\nActividades\nAtención al cliente\nEducación\nUNAM 2019 | 2023\nSobre el candidato\nPuesto deseado\nGestor de Proyectos\nÁrea de especialidad\nAdministrativo\nIdiomas\nInglés - Intermedio\nEspañol - Lengua nativa')
        self.assertIn('Banorre', result['experience'])
        self.assertNotIn('UNAM', result['experience'])
        self.assertEqual(result['education'], 'UNAM 2019 | 2023')
        self.assertEqual(result['languages'], 'Inglés - Intermedio\nEspañol - Lengua nativa')
        self.assertEqual(result['desired_position'], 'Gestor de Proyectos')
        self.assertEqual(result['specialty'], 'Administrativo')
        self.assertEqual(extract_sections('Sin secciones').get('education', ''), '')

if __name__ == '__main__': unittest.main()
