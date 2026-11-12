"""Pruebas que no requieren acceso a Microsoft ni tokens reales."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from src.onedrive_upload import target_url, upload, OneDriveSyncError


class OneDriveUploadTests(unittest.TestCase):
    def test_appfolder_por_defecto(self):
        url = target_url('Sports_Edge_AI.xlsx')
        self.assertEqual(url,
            'https://graph.microsoft.com/v1.0/me/drive/special/approot:/Sports_Edge_AI.xlsx:/content')

    def test_carpeta_proyecto_requiere_opcion_explicita(self):
        self.assertEqual(target_url('Sports_Edge_AI.xlsx', target='project_folder'),
            'https://graph.microsoft.com/v1.0/me/drive/root:/Sports%20Edge%20AI/Sports_Edge_AI.xlsx:/content')

    def test_url_caracteres_especiales(self):
        self.assertIn('An%C3%A1lisis%20NBA.xlsx', target_url('Análisis NBA.xlsx'))

    def test_rechaza_cualquier_ruta_falsa(self):
        for bad in ('../archivo.xlsx', r'otra\\archivo.xlsx', '.oculto.xlsx', 'archivo.csv', ''):
            with self.subTest(bad=bad), self.assertRaises(OneDriveSyncError):
                target_url(bad)

    def test_no_autentica_sin_token(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / 'prueba.xlsx'
            p.write_bytes(b'test')
            with self.assertRaisesRegex(OneDriveSyncError, 'MS_GRAPH_ACCESS_TOKEN'):
                upload(p, '')


if __name__ == '__main__':
    unittest.main()
