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

def test_restricted_data_is_not_served_or_redistributed(monkeypatch):
    import json
    from pathlib import Path
    from src.data_rights import public_series_allowed
    import src.api.main as api
    monkeypatch.delenv('MARKETS_LICENSED_DATA',raising=False)
    assert not public_series_allowed('BAMLC0A0CM')
    assert not public_series_allowed('BAMLH0A0HYM2')
    assert not public_series_allowed('SPY')
    assert public_series_allowed('DFF')
    client=TestClient(api.app)
    assert client.get('/series/BAMLC0A0CM/history').status_code==451
    assert client.get('/analysis/proxies').status_code==451
    path=Path(__file__).parents[1]/'src/data/fred_results.jsonl'
    assert not any(json.loads(line)['series_id'].startswith('BAML') for line in path.read_text().splitlines())

def test_dashboard_does_not_read_or_score_restricted_observations(monkeypatch):
    from unittest.mock import Mock
    import src.indicators.compute as compute
    monkeypatch.delenv('MARKETS_LICENSED_DATA',raising=False)
    connection=Mock();connection.cursor.return_value.fetchall.return_value=[]
    monkeypatch.setattr(compute,'get_connection',lambda:connection)
    monkeypatch.setattr(compute,'_load_sector_definitions',lambda cur:{'example':{'label':'Example','group':'both','sort_order':1,'members':[('BAMLC0A0CM',1,1,1),('DFF',1,1,1)]}})
    def current(cur,sid,day):
        assert not sid.startswith('BAML')
        return {'value':2,'observation_date':day,'vintage_date':day}
    monkeypatch.setattr(compute,'_get_current_value',current)
    monkeypatch.setattr(compute,'_get_historical_values',lambda *a:[1,2,3])
    monkeypatch.setattr(compute,'_compute_spread_series',lambda *a:(None,[],{}))
    monkeypatch.setattr(compute,'_compute_yoy_series',lambda *a:(None,[]))
    monkeypatch.setattr(compute,'_get_staleness',lambda *a:'current')
    result=compute.compute_dashboard()
    assert result['series']['BAMLC0A0CM']['value'] is None
    assert result['sectors']['example']['component_ids']==['DFF']
