include docker/local/.env
# export PROJECT_NAME=mt5
pn = mt5
pf := "./docker/local/docker-compose.yml"

init: ## 開発作成
	make destroy
	docker compose -f $(pf) -p $(pn) build --no-cache
	docker compose -f $(pf) -p $(pn) down --volumes
	docker compose -f $(pf) -p $(pn) up -d
	docker compose -f $(pf) -p $(pn) exec -it mt5 pipenv install --dev

up: ## 開発立ち上げ
	docker compose -f $(pf) -p $(pn) up -d

down: ## 開発down
	docker compose -f $(pf) -p $(pn) down

shell: ## dockerのshellに入る
	docker compose -f $(pf) -p $(pn) exec mt5 bash

check: ## コードのフォーマット
# mt5
	docker compose -f $(pf) -p $(pn) exec -it mt5 pipenv run isort .
	docker compose -f $(pf) -p $(pn) exec -it mt5 pipenv run black .
	docker compose -f $(pf) -p $(pn) exec -it mt5 pipenv run flake8 .
	docker compose -f $(pf) -p $(pn) exec -it mt5 pipenv run mypy .

destroy: ## 開発環境削除
	make down
	if [ -n "$(docker network ls -qf name=$(pn))" ]; then \
		docker network ls -qf name=$(pn) | xargs docker network rm; \
	fi
	if [ -n "$(docker container ls -a -qf name=$(pn))" ]; then \
		docker container ls -a -qf name=$(pn) | xargs docker container rm; \
	fi
	if [ -n "$(docker volume ls -qf name=$(pn))" ]; then \
		docker volume ls -qf name=$(pn) | xargs docker volume rm; \
	fi

push:
	git add .
	git commit -m "Commit at $$(date +'%Y-%m-%d %H:%M:%S')"
	git push origin HEAD

reset-commit: ## mainブランチのコミット履歴を1つにする 使用は控える
	git pull origin HEAD
	git checkout --orphan new-branch-name
	git add .
	git branch -D main
	git branch -m main
	git commit -m "first commit"
	git push origin -f main

test:
	docker compose -f $(pf) -p $(pn) exec -it mt5 pipenv run pytest tests/
