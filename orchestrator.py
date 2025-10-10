#!/usr/bin/env python3
"""
Orquestrador de múltiplas instâncias do Compositor de Músicas Educativas.
Permite rodar N instâncias em paralelo com portas distintas.

Uso:
    python orchestrator.py start --instances 3
    python orchestrator.py stop --instance 1
    python orchestrator.py stop --all
    python orchestrator.py status
"""
import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import time

# Configurações base
BASE_PORT_BACKEND = 8000
BASE_PORT_REDIS = 6379
PROJECT_ROOT = Path(__file__).parent
INSTANCES_FILE = PROJECT_ROOT / ".instances.json"

class InstanceManager:
    """Gerencia múltiplas instâncias da aplicação."""
    
    def __init__(self):
        self.instances_file = INSTANCES_FILE
        self.instances = self._load_instances()
    
    def _load_instances(self):
        """Carrega instâncias ativas do arquivo."""
        if self.instances_file.exists():
            with open(self.instances_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_instances(self):
        """Salva instâncias no arquivo."""
        with open(self.instances_file, 'w') as f:
            json.dump(self.instances, f, indent=2)
    
    def _get_next_instance_id(self):
        """Retorna próximo ID disponível."""
        if not self.instances:
            return 1
        return max(map(int, self.instances.keys())) + 1
    
    def _port_is_available(self, port):
        """Verifica se porta está disponível."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0
    
    def _find_available_ports(self, base_backend, base_redis):
        """Encontra portas disponíveis."""
        backend_port = base_backend
        redis_port = base_redis
        
        # Procurar porta backend disponível
        while not self._port_is_available(backend_port):
            backend_port += 1
            if backend_port > base_backend + 100:
                raise Exception("Não foi possível encontrar porta backend disponível")
        
        # Procurar porta redis disponível
        while not self._port_is_available(redis_port):
            redis_port += 1
            if redis_port > base_redis + 100:
                raise Exception("Não foi possível encontrar porta redis disponível")
        
        return backend_port, redis_port
    
    def start_instance(self, instance_id=None):
        """Inicia uma nova instância."""
        if instance_id is None:
            instance_id = self._get_next_instance_id()
        
        instance_id = str(instance_id)
        
        # Verificar se já existe
        if instance_id in self.instances:
            print(f"❌ Instância {instance_id} já está rodando!")
            return False
        
        # Encontrar portas disponíveis
        backend_port, redis_port = self._find_available_ports(
            BASE_PORT_BACKEND + int(instance_id) - 1,
            BASE_PORT_REDIS + int(instance_id) - 1
        )
        
        print(f"\n🚀 Iniciando instância {instance_id}")
        print(f"   Backend: porta {backend_port}")
        print(f"   Redis: porta {redis_port}")
        
        # Criar diretórios isolados
        data_dir = PROJECT_ROOT / "data" / f"instance_{instance_id}"
        for subdir in ['inputs', 'outputs', 'checkpoints', 'logs']:
            (data_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        # Criar arquivo .env específico
        env_file = PROJECT_ROOT / f".env.instance_{instance_id}"
        self._create_env_file(env_file, instance_id, backend_port, redis_port)
        
        # Criar docker-compose específico
        compose_file = PROJECT_ROOT / f"docker-compose.instance_{instance_id}.yml"
        self._create_compose_file(compose_file, instance_id, backend_port, redis_port)
        
        # Iniciar containers
        try:
            subprocess.run([
                "docker", "compose",
                "-f", str(compose_file),
                "-p", f"autoletras_instance_{instance_id}",
                "up", "-d"
            ], check=True, cwd=PROJECT_ROOT)
            
            # Salvar informações da instância
            self.instances[instance_id] = {
                "id": instance_id,
                "backend_port": backend_port,
                "redis_port": redis_port,
                "started_at": datetime.now().isoformat(),
                "data_dir": str(data_dir),
                "env_file": str(env_file),
                "compose_file": str(compose_file),
                "project_name": f"autoletras_instance_{instance_id}"
            }
            self._save_instances()
            
            print(f"\n✅ Instância {instance_id} iniciada com sucesso!")
            print(f"   🌐 URL: http://localhost:{backend_port}")
            print(f"   📊 Redis: localhost:{redis_port}")
            print(f"   📁 Dados: {data_dir}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao iniciar instância: {e}")
            # Limpar arquivos criados
            env_file.unlink(missing_ok=True)
            compose_file.unlink(missing_ok=True)
            return False
    
    def _create_env_file(self, env_file, instance_id, backend_port, redis_port):
        """Cria arquivo .env para a instância."""
        # Carregar .env base
        base_env = PROJECT_ROOT / ".env"
        if base_env.exists():
            with open(base_env, 'r') as f:
                base_content = f.read()
        else:
            base_content = ""
        
        # Adicionar/sobrescrever variáveis específicas
        env_content = f"""# Instância {instance_id} - Gerado automaticamente
# {datetime.now().isoformat()}

{base_content}

# Configurações da Instância {instance_id}
INSTANCE_ID={instance_id}
PORT={backend_port}
REDIS_HOST=redis_instance_{instance_id}
REDIS_PORT={redis_port}
DATA_DIR=data/instance_{instance_id}
"""
        
        with open(env_file, 'w') as f:
            f.write(env_content)
    
    def _create_compose_file(self, compose_file, instance_id, backend_port, redis_port):
        """Cria docker-compose.yml para a instância."""
        compose_content = f"""
services:
  redis_instance_{instance_id}:
    image: redis:7-alpine
    container_name: redis_instance_{instance_id}
    ports:
      - "{redis_port}:6379"
    volumes:
      - redis_data_instance_{instance_id}:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - autoletras_instance_{instance_id}

  backend_instance_{instance_id}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: backend_instance_{instance_id}
    ports:
      - "{backend_port}:8000"
    volumes:
      - ./data/instance_{instance_id}:/app/data
      - ./backend:/app/backend
      - ./frontend:/app/frontend
    env_file:
      - .env.instance_{instance_id}
    environment:
      - REDIS_HOST=redis_instance_{instance_id}
      - REDIS_PORT=6379
      - PORT=8000
      - INSTANCE_ID={instance_id}
      - PYTHONPATH=/app
    depends_on:
      redis_instance_{instance_id}:
        condition: service_healthy
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    networks:
      - autoletras_instance_{instance_id}

  worker_instance_{instance_id}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: worker_instance_{instance_id}
    volumes:
      - ./data/instance_{instance_id}:/app/data
      - ./backend:/app/backend
    env_file:
      - .env.instance_{instance_id}
    environment:
      - REDIS_HOST=redis_instance_{instance_id}
      - REDIS_PORT=6379
      - INSTANCE_ID={instance_id}
      - PYTHONPATH=/app
    depends_on:
      redis_instance_{instance_id}:
        condition: service_healthy
    command: celery -A backend.celery_worker:celery_app worker --loglevel=info --pool=threads --concurrency=3
    networks:
      - autoletras_instance_{instance_id}

volumes:
  redis_data_instance_{instance_id}:

networks:
  autoletras_instance_{instance_id}:
    driver: bridge
"""
        
        with open(compose_file, 'w') as f:
            f.write(compose_content)
    
    def stop_instance(self, instance_id):
        """Para uma instância específica."""
        instance_id = str(instance_id)
        
        if instance_id not in self.instances:
            print(f"❌ Instância {instance_id} não encontrada!")
            return False
        
        instance = self.instances[instance_id]
        
        print(f"\n🛑 Parando instância {instance_id}...")
        
        try:
            # Parar containers
            subprocess.run([
                "docker", "compose",
                "-f", instance['compose_file'],
                "-p", instance['project_name'],
                "down"
            ], cwd=PROJECT_ROOT)
            
            # Remover arquivos de configuração
            Path(instance['env_file']).unlink(missing_ok=True)
            Path(instance['compose_file']).unlink(missing_ok=True)
            
            # Remover da lista
            del self.instances[instance_id]
            self._save_instances()
            
            print(f"✅ Instância {instance_id} parada com sucesso!")
            print(f"   💾 Dados preservados em: {instance['data_dir']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao parar instância: {e}")
            return False
    
    def stop_all(self):
        """Para todas as instâncias."""
        if not self.instances:
            print("ℹ️  Nenhuma instância rodando")
            return True
        
        print(f"\n🛑 Parando {len(self.instances)} instância(s)...")
        
        for instance_id in list(self.instances.keys()):
            self.stop_instance(instance_id)
        
        print("\n✅ Todas as instâncias foram paradas!")
        return True
    
    def status(self):
        """Mostra status de todas as instâncias."""
        if not self.instances:
            print("\nℹ️  Nenhuma instância rodando")
            return
        
        print(f"\n📊 STATUS DAS INSTÂNCIAS ({len(self.instances)} ativa(s))")
        print("=" * 80)
        
        for instance_id, info in sorted(self.instances.items(), key=lambda x: int(x[0])):
            print(f"\n🔹 Instância {instance_id}")
            print(f"   🌐 Backend: http://localhost:{info['backend_port']}")
            print(f"   📊 Redis: localhost:{info['redis_port']}")
            print(f"   📁 Dados: {info['data_dir']}")
            print(f"   🕐 Iniciada: {info['started_at']}")
            
            # Verificar se containers estão rodando
            try:
                result = subprocess.run([
                    "docker", "compose",
                    "-f", info['compose_file'],
                    "-p", info['project_name'],
                    "ps", "--format", "json"
                ], capture_output=True, text=True, cwd=PROJECT_ROOT)
                
                if result.returncode == 0 and result.stdout:
                    containers = json.loads(result.stdout) if result.stdout.startswith('[') else [json.loads(result.stdout)]
                    running = sum(1 for c in containers if c.get('State') == 'running')
                    print(f"   🐳 Containers: {running}/{len(containers)} rodando")
                else:
                    print(f"   ⚠️  Status desconhecido")
                    
            except Exception as e:
                print(f"   ⚠️  Erro ao verificar: {e}")
        
        print("\n" + "=" * 80)
    
    def start_multiple(self, count):
        """Inicia múltiplas instâncias."""
        print(f"\n🚀 Iniciando {count} instância(s)...")
        
        success_count = 0
        for i in range(count):
            if self.start_instance():
                success_count += 1
                time.sleep(2)  # Delay entre inicializações
        
        print(f"\n✅ {success_count}/{count} instância(s) iniciada(s) com sucesso!")
        
        if success_count > 0:
            self.status()

def main():
    parser = argparse.ArgumentParser(
        description="Orquestrador de Instâncias - Compositor de Músicas Educativas"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponíveis')
    
    # Comando: start
    start_parser = subparsers.add_parser('start', help='Inicia instância(s)')
    start_parser.add_argument('--instances', type=int, default=1,
                            help='Número de instâncias a iniciar (padrão: 1)')
    start_parser.add_argument('--id', type=int,
                            help='ID específico para a instância')
    
    # Comando: stop
    stop_parser = subparsers.add_parser('stop', help='Para instância(s)')
    stop_parser.add_argument('--instance', type=int,
                           help='ID da instância a parar')
    stop_parser.add_argument('--all', action='store_true',
                           help='Para todas as instâncias')
    
    # Comando: status
    subparsers.add_parser('status', help='Mostra status das instâncias')
    
    # Comando: restart
    restart_parser = subparsers.add_parser('restart', help='Reinicia instância')
    restart_parser.add_argument('instance', type=int, help='ID da instância')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = InstanceManager()
    
    if args.command == 'start':
        if args.id:
            manager.start_instance(args.id)
        else:
            manager.start_multiple(args.instances)
    
    elif args.command == 'stop':
        if args.all:
            manager.stop_all()
        elif args.instance:
            manager.stop_instance(args.instance)
        else:
            print("❌ Especifique --instance ID ou --all")
    
    elif args.command == 'status':
        manager.status()
    
    elif args.command == 'restart':
        manager.stop_instance(args.instance)
        time.sleep(2)
        manager.start_instance(args.instance)

if __name__ == "__main__":
    main()