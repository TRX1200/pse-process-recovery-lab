"""Idempotently provision only the named local lab assets in Superset 6.1.0."""
import json
import os
from analytics_tools.bootstrap_superset import environment, ROOT
os.environ.update(environment())
from superset.app import create_app
from superset import db, security_manager


def metric(column, label):
    return {'expressionType':'SIMPLE', 'column':{'column_name':column}, 'aggregate':'AVG',
            'label':label, 'hasCustomLabel':True, 'optionName':'metric_'+column}


def main():
    app = create_app()
    with app.app_context():
        from superset.models.core import Database
        from superset.connectors.sqla.models import SqlaTable
        from superset.models.slice import Slice
        from superset.models.dashboard import Dashboard
        admin = security_manager.find_user(username='lab_admin')
        database = db.session.query(Database).filter_by(database_name='Process Lab (simulation, read only)').one_or_none()
        if database is None:
            database = Database(database_name='Process Lab (simulation, read only)')
            db.session.add(database)
        database.set_sqlalchemy_uri('sqlite:///file:'+(ROOT/'outputs/analytics/lab.sqlite').as_posix()+'?mode=ro&uri=true')
        database.expose_in_sqllab = True
        database.allow_dml = False
        database.allow_ctas = False
        database.allow_run_async = False
        db.session.commit()
        tables = {}
        for name in ['rf_latest_cases', 'rf_latest_frequency', 'rf_cases', 'rf_case_history', 'rf_runs', 'process_results', 'rf_coupled_cases', 'surface_results']:
            table = db.session.query(SqlaTable).filter_by(table_name=name, database_id=database.id).one_or_none()
            if table is None:
                table = SqlaTable(table_name=name, database_id=database.id, owners=[admin])
                db.session.add(table)
                db.session.commit()
            table.fetch_metadata()
            tables[name] = table
        db.session.commit()
        specs = [
            ('RF · 최신 실험 반사 전력 (%)', 'rf_latest_cases', 'echarts_timeseries_bar', 'case_name',
             [metric('reflected_pct','Reflected / %')], []),
            ('RF · 최신 실험 전력 분배 (W)', 'rf_latest_cases', 'echarts_timeseries_bar', 'case_name',
             [metric('bulk_w','Bulk / W'),metric('coil_loss_w','Coil loss / W'),metric('capacitor_loss_w','Cap loss / W')], []),
            ('RF · 주파수별 벌크 흡수 전력', 'rf_latest_frequency', 'echarts_timeseries_line', 'frequency_mhz',
             [metric('bulk_w','Bulk / W')], ['case_name']),
            ('RF · 전체 실행 조건별 지표', 'rf_case_history', 'table', None, [],
             ['created_at','run_id','case_name','coil_q','frequency_mhz','density_1e15_m3','cp_pf','cs_pf','reflected_pct','bulk_w','coil_loss_w','series_cap_rms_v']),
            ('ALD / Etch · 계산 결과와 출처', 'process_results', 'table', None, [],
             ['source_id','model','provenance','evidence','center_depth_nm','width_half_depth_nm','top_film_nm','bottom_film_nm','bottom_top_pct']),
            ('RF · Ar 결합 수지와 전자밀도', 'rf_coupled_cases', 'table', None, [],
             ['run_id','case_name','status','density_m3','te_ev','ion_flux_m2_s','bulk_w','reflected_pct','coil_loss_w']),
            ('ALD / Etch · 초기 요철의 공정 전후 변화', 'surface_results', 'table', None, [],
             ['source_id','model','profile','provenance','grid_nm','rays_per_point','seed','rq_initial_nm','rq_final_nm','left_rq_initial_nm','left_rq_final_nm']),
        ]
        charts=[]
        for title, table_name, viz, xaxis, metrics, columns in specs:
            table=tables[table_name]
            chart=db.session.query(Slice).filter_by(slice_name=title).one_or_none()
            if chart is None:
                chart=Slice(slice_name=title, owners=[admin], datasource_id=table.id,
                            datasource_type='table', datasource_name=table_name, viz_type=viz)
                db.session.add(chart)
            form={'datasource':f'{table.id}__table', 'viz_type':viz, 'time_range':'No filter',
                  'metrics':metrics,'adhoc_filters':[],'row_limit':1000,'show_legend':True,
                  'color_scheme':'supersetColors','extra_form_data':{},'y_axis_format':',.2f'}
            if viz=='table':
                form.update(query_mode='raw',all_columns=columns, order_by_cols=[],table_timestamp_format='smart_date',page_length=15)
                query_columns=columns
            else:
                form.update(x_axis=xaxis, groupby=columns, orientation='vertical', x_axis_title='Frequency / MHz' if columns else '',
                            x_axis_label_rotation=15, truncate_metric=True, order_desc=False, stack='Stack' if len(metrics)>1 else None)
                query_columns=[xaxis,*columns]
            query={'time_range':'No filter','filters':[],'extras':{'having':'','where':''},'columns':query_columns,
                   'metrics':metrics,'orderby':[],'row_limit':1000,'order_desc':False,'is_timeseries':False}
            chart.datasource_id=table.id
            chart.datasource_type='table'
            chart.datasource_name=table_name
            chart.viz_type=viz
            chart.cache_timeout=-1
            chart.description='Calculated simulation data. Not measured equipment data.'
            chart.params=json.dumps(form,ensure_ascii=False)
            chart.query_context=json.dumps({'datasource':{'id':table.id,'type':'table'},'queries':[query],
                'form_data':form,'result_format':'json','result_type':'full','force':False},ensure_ascii=False)
            db.session.commit()
            charts.append(chart)
        dashboard=db.session.query(Dashboard).filter_by(slug='rf-process-lab').one_or_none()
        if dashboard is None:
            dashboard=Dashboard(slug='rf-process-lab',owners=[admin])
            db.session.add(dashboard)
        dashboard.dashboard_title='RF Matching & Process Lab · Simulation'
        dashboard.slices=charts
        dashboard.published=True
        layout={'DASHBOARD_VERSION_KEY':'v2',
                'ROOT_ID':{'id':'ROOT_ID','type':'ROOT','children':['GRID_ID']},
                'GRID_ID':{'id':'GRID_ID','type':'GRID','children':[], 'parents':['ROOT_ID']}}
        groups=[[0,1],[2],[3],[4],[5],[6]]
        for i, indexes in enumerate(groups):
            rid=f'ROW-lab-{i}'
            layout['GRID_ID']['children'].append(rid)
            layout[rid]={'id':rid,'type':'ROW','parents':['ROOT_ID','GRID_ID'],'children':[], 'meta':{'background':'BACKGROUND_TRANSPARENT'}}
            for index in indexes:
                chart=charts[index]
                cid=f'CHART-lab-{chart.id}'
                layout[rid]['children'].append(cid)
                layout[cid]={'id':cid,'type':'CHART','parents':['ROOT_ID','GRID_ID',rid],'children':[],
                    'meta':{'chartId':chart.id,'width':12//len(indexes),'height':48,'sliceName':chart.slice_name}}
        dashboard.position_json=json.dumps(layout,ensure_ascii=False)
        dashboard.json_metadata=json.dumps({'refresh_frequency':0,'color_scheme':'supersetColors','expanded_slices':{},'native_filter_configuration':[]})
        security_manager.sync_role_definitions()
        public=security_manager.find_role('Public')
        for table in tables.values():
            permission=security_manager.add_permission_view_menu('datasource_access',table.get_perm())
            security_manager.add_permission_role(public,permission)
        dashboard.roles=[public]
        db.session.commit()
        print('Dashboard: http://127.0.0.1:8088/superset/dashboard/rf-process-lab/')
        print('Created/updated datasets:',list(tables), 'Charts:',[c.id for c in charts])


if __name__=='__main__':
    main()
