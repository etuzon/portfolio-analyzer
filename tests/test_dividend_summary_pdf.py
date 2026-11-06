import io

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import main
from app.auth import AuthStore
from app.dividend_summary_pdf import build_dividend_summary_pdf


def snapshot(language='en'):
    return {'language': language, 'title': 'Annual dividend summary · 2026' if language=='en' else 'סיכום דיבידנדים שנתי · 2026',
            'context': '03/11/2025 - 03/11/2026. USD amounts. No currency conversion.',
            'columns': ['Security', 'Year / share', 'TTM / share', 'Yield', 'Price', 'Recorded income'],
            'rows': [['BBB\nA test security', 'USD 1.04\n3 distributions', 'USD 1.04', '11.9%', 'USD 8.74\n05/11/2026', 'USD 97.50'],
                     ['EMPTY', 'Unavailable\n0 distributions', 'Unavailable', 'Annual yield unavailable', 'Unavailable', 'No recorded income']]}


def test_summary_pdf_preserves_missing_values_order_and_hebrew_font():
    for language in ('en', 'he'):
        content=build_dividend_summary_pdf(snapshot(language))
        assert content.startswith(b'%PDF-')
        reader=PdfReader(io.BytesIO(content))
        text='\n'.join(page.extract_text() for page in reader.pages)
        assert 'BBB' in text and 'EMPTY' in text
        assert text.index('BBB') < text.index('EMPTY')
        assert 'USD 1.04' in text and 'Annual yield unavailable' in text
        assert '05/11/2026' in text


def test_summary_pdf_rejects_invalid_payload():
    for update in ({'rows': []}, {'columns':['one']}, {'rows':[['bad']]}, {'rows':[['x'*2001]*6]}, {'language':'xx'}):
        with pytest.raises(ValueError):build_dividend_summary_pdf({**snapshot(),**update})


def test_pdf_export_is_authenticated_read_only_for_viewers_and_requires_csrf(tmp_path, monkeypatch):
    auth=AuthStore(tmp_path/'auth.sqlite3');auth.initialize()
    user=auth.create_user({'username':'pdfviewer','first_name':'PDF','last_name':'Viewer','role':'Viewer','password':'Pdf-Viewer-Test-2026!'})
    with auth._connect() as connection:connection.execute('update app_users set must_change_password=0 where id=?',(user['id'],))
    monkeypatch.setattr(main,'auth_store',auth)
    client=TestClient(main.app,base_url='https://localhost:6443')
    assert client.post('/api/portfolio/dividend-calendar.pdf',json=snapshot()).status_code==401
    main._login_failures.clear()
    session=client.post('/api/auth/login',json={'username':'pdfviewer','password':'Pdf-Viewer-Test-2026!'}).json()
    assert client.post('/api/portfolio/dividend-calendar.pdf',json=snapshot()).status_code==403
    response=client.post('/api/portfolio/dividend-calendar.pdf',json=snapshot(),headers={'X-CSRF-Token':session['csrf_token']})
    assert response.status_code==200
    assert response.headers['content-type']=='application/pdf'
    assert response.content.startswith(b'%PDF-')
    assert 'attachment' in response.headers['content-disposition']


def test_pdf_paginates_and_escapes_user_labels_without_losing_rows():
    payload=snapshot()
    payload['rows']=[[f'ROW-{index:03d} <b>literal</b>', 'USD 1.00', 'USD 1.00', '1%', 'USD 100\n06/11/2026', 'USD 10'] for index in range(90)]
    reader=PdfReader(io.BytesIO(build_dividend_summary_pdf(payload)))
    assert len(reader.pages)>1
    text='\n'.join(page.extract_text() for page in reader.pages)
    for index in range(90):assert f'ROW-{index:03d}' in text
    assert '<b>literal</b>' in text
    assert all('Recorded income' in page.extract_text() for page in reader.pages)
