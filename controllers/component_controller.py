from flask import Blueprint, request, jsonify
from services.componente_service import ComponenteService
computador_bp = Blueprint('computador_bp', __name__)

# Importar la sesión de la base de datos desde config/database.py
from config.database import get_db_session

class LazyComponentService:
    def __init__(self):
        self._service = None

    def __getattr__(self, name):
        if self._service is None:
            self._service = ComponenteService(get_db_session())
        return getattr(self._service, name)


service = LazyComponentService()


@computador_bp.route('/computadores', methods=['GET'])
def get_computadores():
    """
    GET /computadores
    Recupera y retorna todos los computadores registrados en el sistema.
    Utiliza la capa de servicios para obtener la lista completa de computadores.
    No recibe parámetros.
    Respuesta: JSON con la lista de computadores.
    """
    computadores = service.listar_computadores()
    return jsonify([{
        'id': c.id,
        'cpu': c.cpu,
        'ram': c.ram,
        'almacenamiento': c.almacenamiento,
        'gpu': c.gpu,
        'so': c.so
    } for c in computadores]), 200


@computador_bp.route('/computadores/<int:computador_id>', methods=['GET'])
def get_computador(computador_id):
    """
    GET /computadores/<computador_id>
    Recupera la información de un computador específico por su ID.
    Parámetros:
        computador_id (int): ID del computador a consultar (en la URL).
    Respuesta: JSON con los datos del computador o 404 si no existe.
    """
    computador = service.obtener_computador(computador_id)
    if computador:
        return jsonify({
            'id': computador.id,
            'cpu': computador.cpu,
            'ram': computador.ram,
            'almacenamiento': computador.almacenamiento,
            'gpu': computador.gpu,
            'so': computador.so
        }), 200
    return jsonify({'error': 'Computador no encontrado'}), 404


@computador_bp.route('/computadores', methods=['POST'])
def create_computador():
    """
    POST /computadores
    Crea un nuevo computador.
    Parámetros esperados (JSON):
        cpu (str): Procesador.
        ram (int): Memoria RAM en GB.
        almacenamiento (str): Disco duro o SSD.
        gpu (str): Tarjeta gráfica (opcional).
        so (str): Sistema operativo.
    Respuesta: JSON con los datos del computador creado.
    """
    data = request.get_json()
    cpu = data.get('cpu')
    ram = data.get('ram')
    almacenamiento = data.get('almacenamiento')
    gpu = data.get('gpu')
    so = data.get('so')

    if not cpu or not ram or not almacenamiento:
        return jsonify({'error': 'CPU, RAM y almacenamiento son obligatorios'}), 400

    computador = service.crear_computador(cpu, ram, almacenamiento, gpu, so)
    return jsonify({
        'id': computador.id,
        'cpu': computador.cpu,
        'ram': computador.ram,
        'almacenamiento': computador.almacenamiento,
        'gpu': computador.gpu,
        'so': computador.so
    }), 201


@computador_bp.route('/computadores/<int:computador_id>', methods=['PUT'])
def update_computador(computador_id):
    """
    PUT /computadores/<computador_id>
    Actualiza la información de un computador existente.
    Parámetros:
        computador_id (int): ID del computador a actualizar (en la URL).
        cpu, ram, almacenamiento, gpu, so (JSON en el cuerpo).
    Respuesta: JSON con los datos del computador actualizado o error si no existe.
    """
    data = request.get_json()
    computador = service.actualizar_computador(
        computador_id,
        data.get('cpu'),
        data.get('ram'),
        data.get('almacenamiento'),
        data.get('gpu'),
        data.get('so')
    )
    if computador:
        return jsonify({
            'id': computador.id,
            'cpu': computador.cpu,
            'ram': computador.ram,
            'almacenamiento': computador.almacenamiento,
            'gpu': computador.gpu,
            'so': computador.so
        }), 200
    return jsonify({'error': 'Computador no encontrado'}), 404


@computador_bp.route('/computadores/<int:computador_id>', methods=['DELETE'])
def delete_computador(computador_id):
    """
    DELETE /computadores/<computador_id>
    Elimina un computador específico por su ID.
    Parámetros:
        computador_id (int): ID del computador a eliminar (en la URL).
    Respuesta: JSON con mensaje de éxito o error si no existe.
    """
    computador = service.eliminar_computador(computador_id)
    if computador:
        return jsonify({'message': 'Computador eliminado'}), 200
    return jsonify({'error': 'Computador no encontrado'}), 404
