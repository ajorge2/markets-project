from fastapi.testclient import TestClient

def test_public_reads_and_operator_writes(monkeypatch):
    import src.api.main as api
    client=TestClient(api.app)
    assert client.get('/health').status_code==200
    for method,path in [('post','/analysis-plots'),('put','/sectors/example/weights'),('delete','/analysis-plots/example'),('post','/data/catch-up')]:
        assert getattr(client,method)(path).status_code==403
    monkeypatch.setenv('MARKETS_ADMIN_TOKEN','operator-secret-for-test')
    assert client.post('/unknown',headers={'Authorization':'Bearer wrong'}).status_code==403
    assert client.post('/unknown',headers={'Authorization':'Bearer operator-secret-for-test'}).status_code==404
