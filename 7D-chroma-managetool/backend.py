#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChromaDB 管理工具后端服务器
提供 REST API 用于管理 ChromaDB
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import chromadb
from chromadb.config import Settings
import os
import json
import csv
import io
import time
import logging
from datetime import datetime
from collections import deque
import threading
import psutil

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局变量
chroma_client = None
current_collection = None

# ==================== 新增：日志系统 ====================
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../chromadb_operations.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 操作日志队列（内存中保存最近1000条）
operation_logs = deque(maxlen=1000)

def log_operation(operation_type, details, status='success', error=None):
    """记录操作日志"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'operation': operation_type,
        'details': details,
        'status': status,
        'error': str(error) if error else None,
        'collection': current_collection.name if current_collection else None
    }
    operation_logs.append(log_entry)
    
    if status == 'success':
        logger.info(f"{operation_type}: {details}")
    else:
        logger.error(f"{operation_type} FAILED: {details} - {error}")
    
    return log_entry

# ==================== 新增：性能监控 ====================
# 性能指标存储
performance_metrics = {
    'query_times': deque(maxlen=100),  # 最近100次查询时间
    'operation_counts': {
        'queries': 0,
        'inserts': 0,
        'deletes': 0,
        'updates': 0
    },
    'slow_queries': deque(maxlen=50),  # 慢查询记录
    'start_time': time.time()
}

def record_performance(operation_type, duration, details=None):
    """记录性能指标"""
    if operation_type not in performance_metrics['operation_counts']:
        performance_metrics['operation_counts'][operation_type] = 0
    
    performance_metrics['operation_counts'][operation_type] += 1
    
    if operation_type == 'queries':
        performance_metrics['query_times'].append(duration)
        
        # 记录慢查询（>1秒）
        if duration > 1.0:
            performance_metrics['slow_queries'].append({
                'timestamp': datetime.now().isoformat(),
                'duration': duration,
                'details': details
            })

# ==================== 连接管理 ====================

@app.route('/api/connect', methods=['POST'])
def connect():
    """连接到 ChromaDB"""
    global chroma_client
    try:
        data = request.json
        host = data.get('host', 'localhost')
        port = data.get('port', 8000)
        
        # 连接到 ChromaDB 服务器（HTTP模式）
        try:
            chroma_client = chromadb.HttpClient(
                host=host,
                port=port
            )
            # 测试连接
            chroma_client.heartbeat()
            connection_mode = 'HTTP Server'
        except Exception as http_error:
            # 如果HTTP连接失败，尝试使用持久化的本地客户端
            try:
                chroma_client = chromadb.PersistentClient(path="./chroma_data")
                connection_mode = 'Persistent Local'
            except Exception as local_error:
                raise Exception(f"无法连接: HTTP模式失败 ({str(http_error)}), 本地模式也失败 ({str(local_error)})")
        
        log_operation('CONNECT', f'连接到 {host}:{port} ({connection_mode})', 'success')
        
        return jsonify({
            'success': True,
            'message': f'成功连接到 ChromaDB ({connection_mode})',
            'host': host,
            'port': port,
            'mode': connection_mode
        })
    except Exception as e:
        log_operation('CONNECT', f'连接失败', 'error', e)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """断开连接"""
    global chroma_client, current_collection
    chroma_client = None
    current_collection = None
    return jsonify({'success': True, 'message': '已断开连接'})

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取连接状态"""
    return jsonify({
        'connected': chroma_client is not None,
        'current_collection': current_collection.name if current_collection else None
    })

# ==================== 集合管理 ====================

@app.route('/api/collections', methods=['GET'])
def list_collections():
    """获取所有集合"""
    if not chroma_client:
        return jsonify({'success': False, 'error': '未连接到数据库'}), 400
    
    try:
        collections = chroma_client.list_collections()
        collection_list = [{'name': col.name, 'count': col.count()} for col in collections]
        
        return jsonify({
            'success': True,
            'collections': collection_list
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/collections', methods=['POST'])
def create_collection():
    """创建新集合"""
    if not chroma_client:
        return jsonify({'success': False, 'error': '未连接到数据库'}), 400
    
    try:
        data = request.json
        name = data.get('name')
        
        if not name:
            return jsonify({'success': False, 'error': '集合名称不能为空'}), 400
        
        collection = chroma_client.create_collection(name=name)
        
        return jsonify({
            'success': True,
            'message': f'成功创建集合: {name}',
            'collection': {'name': collection.name, 'count': collection.count()}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/collections/<name>', methods=['DELETE'])
def delete_collection(name):
    """删除集合"""
    if not chroma_client:
        return jsonify({'success': False, 'error': '未连接到数据库'}), 400
    
    try:
        chroma_client.delete_collection(name=name)
        return jsonify({
            'success': True,
            'message': f'成功删除集合: {name}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/collections/<name>/select', methods=['POST'])
def select_collection(name):
    """选择当前集合"""
    global current_collection
    
    if not chroma_client:
        return jsonify({'success': False, 'error': '未连接到数据库'}), 400
    
    try:
        current_collection = chroma_client.get_collection(name=name)
        
        return jsonify({
            'success': True,
            'message': f'已选择集合: {name}',
            'collection': {
                'name': current_collection.name,
                'count': current_collection.count()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 数据操作 ====================

@app.route('/api/documents', methods=['POST'])
def add_documents():
    """添加文档"""
    if not current_collection:
        return jsonify({'success': False, 'error': '请先选择集合'}), 400
    
    start_time = time.time()
    try:
        data = request.json
        documents = data.get('documents', [])
        ids = data.get('ids', [])
        metadatas = data.get('metadatas', None)
        
        if not documents:
            return jsonify({'success': False, 'error': '文档列表不能为空'}), 400
        
        # 自动生成 IDs
        if not ids:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
        
        current_collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas
        )
        
        duration = time.time() - start_time
        record_performance('inserts', duration, f'添加 {len(documents)} 个文档')
        log_operation('ADD_DOCUMENTS', f'添加了 {len(documents)} 个文档', 'success')
        
        return jsonify({
            'success': True,
            'message': f'成功添加 {len(documents)} 个文档',
            'ids': ids,
            'count': current_collection.count(),
            'duration': f'{duration:.3f}s'
        })
    except Exception as e:
        log_operation('ADD_DOCUMENTS', '添加文档失败', 'error', e)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documents/query', methods=['POST'])
def query_documents():
    """查询文档"""
    if not current_collection:
        return jsonify({'success': False, 'error': '请先选择集合'}), 400
    
    start_time = time.time()
    try:
        data = request.json
        query_texts = data.get('query_texts', [])
        n_results = data.get('n_results', 10)
        where = data.get('where', None)
        
        if not query_texts:
            return jsonify({'success': False, 'error': '查询文本不能为空'}), 400
        
        results = current_collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where
        )
        
        duration = time.time() - start_time
        record_performance('queries', duration, f'查询: {query_texts[0][:50]}...')
        log_operation('QUERY', f'查询文本: {query_texts[0][:50]}... 返回 {n_results} 条结果', 'success')
        
        return jsonify({
            'success': True,
            'results': results,
            'duration': f'{duration:.3f}s'
        })
    except Exception as e:
        log_operation('QUERY', '查询失败', 'error', e)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """获取所有文档"""
    if not current_collection:
        return jsonify({'success': False, 'error': '请先选择集合'}), 400
    
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        results = current_collection.get(
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            'success': True,
            'count': current_collection.count(),
            'data': results
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """删除文档"""
    if not current_collection:
        return jsonify({'success': False, 'error': '请先选择集合'}), 400
    
    start_time = time.time()
    try:
        current_collection.delete(ids=[doc_id])
        
        duration = time.time() - start_time
        record_performance('deletes', duration)
        log_operation('DELETE_DOCUMENT', f'删除文档: {doc_id}', 'success')
        
        return jsonify({
            'success': True,
            'message': f'成功删除文档: {doc_id}',
            'count': current_collection.count(),
            'duration': f'{duration:.3f}s'
        })
    except Exception as e:
        log_operation('DELETE_DOCUMENT', f'删除文档失败: {doc_id}', 'error', e)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documents/update', methods=['PUT'])
def update_document():
    """更新文档"""
    if not current_collection:
        return jsonify({'success': False, 'error': '请先选择集合'}), 400
    
    start_time = time.time()
    try:
        data = request.json
        ids = data.get('ids', [])
        documents = data.get('documents', None)
        metadatas = data.get('metadatas', None)
        
        if not ids:
            return jsonify({'success': False, 'error': 'IDs 不能为空'}), 400
        
        current_collection.update(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        duration = time.time() - start_time
        record_performance('updates', duration, f'更新 {len(ids)} 个文档')
        log_operation('UPDATE_DOCUMENTS', f'更新了 {len(ids)} 个文档', 'success')
        
        return jsonify({
            'success': True,
            'message': f'成功更新 {len(ids)} 个文档',
            'duration': f'{duration:.3f}s'
        })
    except Exception as e:
        log_operation('UPDATE_DOCUMENTS', '更新文档失败', 'error', e)
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 统计信息 ====================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    if not current_collection:
        return jsonify({'success': False, 'error': '请先选择集合'}), 400
    
    try:
        # 获取样本数据以获取向量维度
        sample = current_collection.get(limit=1, include=['embeddings'])
        vector_dim = 0
        if sample['embeddings'] is not None and len(sample['embeddings']) > 0 and sample['embeddings'][0] is not None:
            vector_dim = len(sample['embeddings'][0])
        
        return jsonify({
            'success': True,
            'stats': {
                'name': current_collection.name,
                'count': current_collection.count(),
                'vector_dimension': vector_dim
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 新增功能1：批量删除 ====================

@app.route('/api/documents/batch-delete', methods=['POST'])
def batch_delete_documents():
    """批量删除文档"""
    if not chroma_client:
        return jsonify({'success': False, 'error': '请先连接到数据库'}), 400
    
    start_time = time.time()
    try:
        data = request.json
        collection_name = data.get('collection')
        ids = data.get('ids', [])
        where = data.get('where', None)  # 按条件删除
        
        # 获取集合
        if collection_name:
            collection = chroma_client.get_collection(name=collection_name)
        elif current_collection:
            collection = current_collection
        else:
            return jsonify({'success': False, 'error': '请先选择集合'}), 400
        
        deleted_count = 0
        
        if ids:
            # 按ID批量删除
            collection.delete(ids=ids)
            deleted_count = len(ids)
            details = f'删除了 {deleted_count} 个文档 (按ID)'
        elif where:
            # 按条件删除
            docs = collection.get(where=where)
            if docs['ids']:
                collection.delete(ids=docs['ids'])
                deleted_count = len(docs['ids'])
                details = f'删除了 {deleted_count} 个文档 (按条件: {where})'
            else:
                details = '未找到匹配的文档'
        else:
            return jsonify({'success': False, 'error': '必须提供 ids 或 where 条件'}), 400
        
        duration = time.time() - start_time
        record_performance('deletes', duration, details)
        log_operation('BATCH_DELETE', details, 'success')
        
        return jsonify({
            'success': True,
            'message': details,
            'deleted_count': deleted_count,
            'remaining_count': collection.count(),
            'duration': f'{duration:.3f}s'
        })
    except Exception as e:
        log_operation('BATCH_DELETE', '批量删除失败', 'error', e)
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 新增功能2：数据导出/导入 ====================

@app.route('/api/export', methods=['POST'])
def export_data():
    """导出集合数据为JSON"""
    if not chroma_client:
        return jsonify({'success': False, 'error': '请先连接到数据库'}), 400
    
    start_time = time.time()
    try:
        data = request.json
        collection_name = data.get('collection')
        format_type = data.get('format', 'json')  # json 或 csv
        limit = data.get('limit', None)
        
        # 获取集合
        if collection_name:
            collection = chroma_client.get_collection(name=collection_name)
        elif current_collection:
            collection = current_collection
        else:
            return jsonify({'success': False, 'error': '请先选择集合'}), 400
        
        # 获取所有数据
        results = collection.get(
            limit=limit,
            include=['documents', 'metadatas', 'embeddings']
        )
        
        if format_type == 'json':
            # JSON格式导出 - 将numpy数组转换为列表
            embeddings_list = None
            if results['embeddings'] is not None and len(results['embeddings']) > 0:
                embeddings_list = [emb.tolist() if hasattr(emb, 'tolist') else emb for emb in results['embeddings']]
            
            export_data = {
                'collection_name': collection.name,
                'export_time': datetime.now().isoformat(),
                'count': len(results['ids']),
                'data': {
                    'ids': results['ids'],
                    'documents': results['documents'],
                    'metadatas': results['metadatas'],
                    'embeddings': embeddings_list
                }
            }
            
            output = io.BytesIO()
            output.write(json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8'))
            output.seek(0)
            
            filename = f"{collection.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        elif format_type == 'csv':
            # CSV格式导出（不包含embeddings）
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow(['ID', 'Document', 'Metadata'])
            
            # 写入数据
            for i in range(len(results['ids'])):
                writer.writerow([
                    results['ids'][i],
                    results['documents'][i] if results['documents'] else '',
                    json.dumps(results['metadatas'][i]) if results['metadatas'] and results['metadatas'][i] else '{}'
                ])
            
            output.seek(0)
            output_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
            filename = f"{collection.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            output = output_bytes
        else:
            return jsonify({'success': False, 'error': '不支持的导出格式'}), 400
        
        duration = time.time() - start_time
        log_operation('EXPORT', f'导出 {len(results["ids"])} 条数据为 {format_type}', 'success')
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json' if format_type == 'json' else 'text/csv'
        )
        
    except Exception as e:
        log_operation('EXPORT', '导出失败', 'error', e)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/import', methods=['POST'])
def import_data():
    """导入数据到集合"""
    if not chroma_client:
        return jsonify({'success': False, 'error': '请先连接到数据库'}), 400
    
    start_time = time.time()
    try:
        # 检查是否有文件上传
        if 'file' in request.files:
            file = request.files['file']
            file_content = file.read().decode('utf-8')
            collection_name = request.form.get('collection')
            
            if file.filename.endswith('.json'):
                import_data = json.loads(file_content)
                data = import_data.get('data', import_data)
            elif file.filename.endswith('.csv'):
                reader = csv.DictReader(io.StringIO(file_content))
                ids = []
                documents = []
                metadatas = []
                
                for row in reader:
                    ids.append(row['ID'])
                    documents.append(row['Document'])
                    metadatas.append(json.loads(row.get('Metadata', '{}')))
                
                data = {
                    'ids': ids,
                    'documents': documents,
                    'metadatas': metadatas
                }
            else:
                return jsonify({'success': False, 'error': '不支持的文件格式'}), 400
        else:
            # JSON数据从请求体
            request_data = request.json
            collection_name = request_data.get('collection')
            data = request_data.get('data', request_data)
        
        # 获取集合
        if collection_name:
            collection = chroma_client.get_collection(name=collection_name)
        elif current_collection:
            collection = current_collection
        else:
            return jsonify({'success': False, 'error': '请先选择集合'}), 400
        
        # 导入数据
        ids = data.get('ids', [])
        documents = data.get('documents', [])
        metadatas = data.get('metadatas', None)
        embeddings = data.get('embeddings', None)
        
        if not ids or not documents:
            return jsonify({'success': False, 'error': '数据格式错误，需要 ids 和 documents'}), 400
        
        # 添加到集合
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )
        
        duration = time.time() - start_time
        record_performance('inserts', duration, f'导入 {len(ids)} 条数据')
        log_operation('IMPORT', f'成功导入 {len(ids)} 条数据', 'success')
        
        return jsonify({
            'success': True,
            'message': f'成功导入 {len(ids)} 条数据',
            'count': len(ids),
            'total_count': collection.count(),
            'duration': f'{duration:.3f}s'
        })
        
    except Exception as e:
        log_operation('IMPORT', '导入失败', 'error', e)
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 新增功能3：性能监控 ====================

@app.route('/api/metrics/performance', methods=['GET'])
def get_performance_metrics():
    """获取性能指标"""
    try:
        query_times = list(performance_metrics['query_times'])
        
        metrics = {
            'system': {
                'uptime': time.time() - performance_metrics['start_time'],
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent
            },
            'operations': performance_metrics['operation_counts'],
            'queries': {
                'total': performance_metrics['operation_counts'].get('queries', 0),
                'avg_time': sum(query_times) / len(query_times) if query_times else 0,
                'min_time': min(query_times) if query_times else 0,
                'max_time': max(query_times) if query_times else 0,
                'recent_times': query_times[-10:]  # 最近10次查询时间
            },
            'slow_queries': list(performance_metrics['slow_queries'])[-10:],  # 最近10个慢查询
            'collections': {
                'current': current_collection.name if current_collection else None,
                'total': len(chroma_client.list_collections()) if chroma_client else 0
            }
        }
        
        return jsonify({
            'success': True,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/metrics/realtime', methods=['GET'])
def get_realtime_metrics():
    """获取实时指标（轻量级）"""
    try:
        return jsonify({
            'success': True,
            'metrics': {
                'cpu': psutil.cpu_percent(interval=0.1),
                'memory': psutil.virtual_memory().percent,
                'operations_count': sum(performance_metrics['operation_counts'].values()),
                'current_collection_size': current_collection.count() if current_collection else 0,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 新增功能4：操作日志 ====================

@app.route('/api/logs/operations', methods=['GET'])
def get_operation_logs():
    """获取操作日志"""
    try:
        limit = request.args.get('limit', 100, type=int)
        operation_type = request.args.get('type', None)
        status = request.args.get('status', None)
        
        # 过滤日志
        logs = list(operation_logs)
        
        if operation_type:
            logs = [log for log in logs if log['operation'] == operation_type]
        
        if status:
            logs = [log for log in logs if log['status'] == status]
        
        # 限制数量
        logs = logs[-limit:]
        logs.reverse()  # 最新的在前
        
        return jsonify({
            'success': True,
            'logs': logs,
            'total': len(logs)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/logs/export', methods=['GET'])
def export_logs():
    """导出日志文件"""
    try:
        log_file_path = '../chromadb_operations.log'
        
        if os.path.exists(log_file_path):
            return send_file(
                log_file_path,
                as_attachment=True,
                download_name=f'chromadb_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
            )
        else:
            return jsonify({'success': False, 'error': '日志文件不存在'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """清空内存日志"""
    try:
        operation_logs.clear()
        log_operation('CLEAR_LOGS', '清空操作日志', 'success')
        
        return jsonify({
            'success': True,
            'message': '日志已清空'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 新增功能5：Python命令执行 ====================

@app.route('/api/execute', methods=['POST'])
def execute_command():
    """执行Python命令"""
    if not chroma_client:
        return jsonify({'success': False, 'error': '请先连接到数据库'}), 400
    
    start_time = time.time()
    try:
        data = request.json
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({'success': False, 'error': '命令不能为空'}), 400
        
        # 准备执行环境
        exec_globals = {
            'chromadb': chromadb,
            'chroma_client': chroma_client,
            'client': chroma_client,
            'current_collection': current_collection,
            'collection': current_collection
        }
        exec_locals = {}
        
        # 捕获输出
        import sys
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        result = None
        error = None
        
        try:
            # 尝试作为表达式执行（获取返回值）
            try:
                result = eval(command, exec_globals, exec_locals)
            except SyntaxError:
                # 如果不是表达式，作为语句执行
                exec(command, exec_globals, exec_locals)
                # 检查是否有最后一个表达式的值
                if exec_locals:
                    # 获取最后赋值的变量（如果有）
                    last_var = list(exec_locals.keys())[-1] if exec_locals else None
                    if last_var:
                        result = exec_locals[last_var]
            
            # 获取打印输出
            output = sys.stdout.getvalue()
            
        except Exception as e:
            error = str(e)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        
        duration = time.time() - start_time
        
        if error:
            log_operation('EXECUTE_CMD', f'命令执行失败: {command[:50]}...', 'error', error)
            return jsonify({
                'success': False,
                'error': error,
                'command': command,
                'duration': f'{duration:.3f}s'
            }), 400
        else:
            log_operation('EXECUTE_CMD', f'执行命令: {command[:50]}...', 'success')
            
            # 构造响应
            response_data = {
                'success': True,
                'command': command,
                'duration': f'{duration:.3f}s'
            }
            
            # 添加结果
            if result is not None:
                response_data['result'] = str(result)
            
            if output:
                response_data['output'] = output
            
            # 如果既没有result也没有output，返回成功消息
            if result is None and not output:
                response_data['message'] = '命令执行成功'
            
            return jsonify(response_data)
        
    except Exception as e:
        log_operation('EXECUTE_CMD', '命令执行异常', 'error', e)
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 前端页面 ====================

@app.route('/')
def index():
    """提供前端页面"""
    html_path = os.path.join(os.path.dirname(__file__), 'chromadb_management_tool.html')
    if os.path.exists(html_path):
        return send_file(html_path)
    else:
        return """
        <h1>ChromaDB 管理工具后端 v0.2</h1>
        <p>✅ API 服务已启动</p>
        <p>⚠️ 前端页面文件未找到，请确保 chromadb_management_tool.html 在同一目录下</p>
        
        <h2>📡 基础 API：</h2>
        <ul>
            <li>POST /api/connect - 连接数据库</li>
            <li>POST /api/disconnect - 断开连接</li>
            <li>GET /api/status - 获取连接状态</li>
        </ul>
        
        <h2>📁 集合管理：</h2>
        <ul>
            <li>GET /api/collections - 获取集合列表</li>
            <li>POST /api/collections - 创建集合</li>
            <li>DELETE /api/collections/&lt;name&gt; - 删除集合</li>
            <li>POST /api/collections/&lt;name&gt;/select - 选择集合</li>
        </ul>
        
        <h2>📄 文档操作：</h2>
        <ul>
            <li>POST /api/documents - 添加文档</li>
            <li>POST /api/documents/query - 查询文档</li>
            <li>GET /api/documents - 获取文档列表</li>
            <li>PUT /api/documents/update - 更新文档</li>
            <li>DELETE /api/documents/&lt;doc_id&gt; - 删除文档</li>
            <li><strong>POST /api/documents/batch-delete - 批量删除 🆕</strong></li>
        </ul>
        
        <h2>📊 数据导入导出：</h2>
        <ul>
            <li><strong>POST /api/export - 导出数据 (JSON/CSV) 🆕</strong></li>
            <li><strong>POST /api/import - 导入数据 🆕</strong></li>
        </ul>
        
        <h2>📈 性能监控：</h2>
        <ul>
            <li><strong>GET /api/metrics/performance - 获取性能指标 🆕</strong></li>
            <li><strong>GET /api/metrics/realtime - 实时指标 🆕</strong></li>
        </ul>
        
        <h2>📝 操作日志：</h2>
        <ul>
            <li><strong>GET /api/logs/operations - 获取操作日志 🆕</strong></li>
            <li><strong>GET /api/logs/export - 导出日志文件 🆕</strong></li>
            <li><strong>POST /api/logs/clear - 清空日志 🆕</strong></li>
        </ul>
        
        <h2>⚙️ Python命令执行：</h2>
        <ul>
            <li><strong>POST /api/execute - 执行Python命令 🆕</strong></li>
        </ul>
        
        <h2>ℹ️ 统计信息：</h2>
        <ul>
            <li>GET /api/stats - 获取统计信息</li>
        </ul>
        """

# ==================== 主程序 ====================

if __name__ == '__main__':
    print("="*60)
    print("🚀 ChromaDB 管理工具后端服务器 v0.2")
    print("="*60)
    print("\n📡 服务地址: http://localhost:5001")
    print("📄 前端界面: http://localhost:5001")
    print("\n🆕 新增功能：")
    print("  ✅ 批量删除文档")
    print("  ✅ 数据导入/导出 (JSON/CSV)")
    print("  ✅ 实时性能监控")
    print("  ✅ 操作日志记录")
    print("  ✅ Python命令执行 (支持Ctrl+Enter快捷键)")
    print("\n💡 依赖安装:")
    print("   pip install flask flask-cors chromadb psutil")
    print("\n📝 日志文件: chromadb_operations.log")
    print("="*60 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )
