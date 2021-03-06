IMAGE=doccreator
NAME=$(IMAGE)1
NAMESPACE=default
DNSNAME=localhost
WEBUSER=demo
WEBPASS_CMD=echo 'Test-It!'
#WEBPASS_CMD=aws secretsmanager --profile someprofile get-secret-value --secret-id $(WEBUSER) --no-cli-pager --output json | jq -r .SecretString
WEBPASS=$(shell $(WEBPASS_CMD))
PYTHON_MODULES=flask python-dotenv PyYAML gunicorn jsonpath-ng
VENV=.venv
export BUILDTAG:=$(shell date +%Y%m%d.%H%M%S)

HELM_OPTS:=--set image.repository=$(DOCKER_REGISTRY)/$(IMAGE) --set image.tag=$(BUILDTAG) --set ingresspath.dnsname=$(DNSNAME) --set ingresspath.basicauthsecret=basicauth-$(IMAGE) --set image.pullPolicy=Always
APP_URL:=$(shell echo "https://$(DNSNAME)/$(NAME)/" | sed -e "s|://|://$(WEBUSER):$(WEBPASS)@|")

all: install wait ping

requirements.txt:
	python3 -m pip install --user virtualenv
	python3 -m virtualenv $(VENV) && . $(VENV)/bin/activate && python3 -m pip install --upgrade pip && python3 -m pip install $(PYTHON_MODULES)
	. $(VENV)/bin/activate && python3 -m pip freeze --all | grep -v pkg_resources==0.0.0 > requirements.txt

$(VENV): requirements.txt
	python3 -m pip install --user virtualenv
	python3 -m virtualenv $(VENV) && . $(VENV)/bin/activate && python3 -m pip install -r requirements.txt
	touch $(VENV)/.stamp

$(VENV)/.stamp: $(VENV)

venv-setup: $(VENV)/.stamp

run: $(VENV)/.stamp
	. $(VENV)/bin/activate && FLASK_ENV=development VERBOSE=2 python3 ./app.py

run-gunicorn: $(VENV)/.stamp
	. $(VENV)/bin/activate && gunicorn --bind 0.0.0.0:8888 --access-logfile - wsgi:app

clean:
	rm -rf $(VENV)
	find -iname "*.pyc" -delete 2>/dev/null || true
	find -name __pycache__ -type d -exec rm -rf '{}' ';' 2>/dev/null || true

distclean: clean
	rm -rf requirements.txt
	rm -rf id_rsa id_rsa.pub

image: $(VENV)/.stamp
	docker build --build-arg BUILDTAG=$(BUILDTAG) -t $(IMAGE) .
	docker tag $(IMAGE) $(DOCKER_REGISTRY)/$(IMAGE):$(BUILDTAG)
	docker push $(DOCKER_REGISTRY)/$(IMAGE):$(BUILDTAG)

imagerun: $(VENV)/.stamp
	docker build -t $(IMAGE) .
	docker run -it -p 8008:5000 $(IMAGE)

install-dry:
	helm install --dry-run --debug $(HELM_OPTS) --namespace=$(NAMESPACE) $(NAME) ./doccreator-helm

install: image ssh-secret basicauth_secret_update
	helm lint ./doccreator-helm
	helm upgrade --install $(HELM_OPTS) --namespace=$(NAMESPACE) $(NAME) ./doccreator-helm

basicauth_secret_update:
	$(WEBPASS_CMD) | htpasswd -i -n "$(WEBUSER)" | kubectl --namespace=$(NAMESPACE) create secret generic basicauth-$(IMAGE) --from-file=auth=/dev/stdin --dry-run=client --output=yaml --save-config | kubectl apply -f -

ssh-key:
	ssh-keygen -N '' -f ssh-key

ssh-secret: ssh-key
	kubectl --namespace=$(NAMESPACE) create secret generic $(NAME)-ssh-key --from-file=id_rsa=ssh-key --from-file=id_rsa.pub=ssh-key.pub --dry-run=client --output=yaml --save-config | kubectl apply -f -

wait:
	sleep 15

uninstall:
	-helm uninstall --namespace=$(NAMESPACE) $(NAME)
	-kubectl --namespace=$(NAMESPACE) delete secret basicauth-$(IMAGE)
	-kubectl --namespace=$(NAMESPACE) delete secret $(NAME)-ssh-key

ping:
	curl -si "$(APP_URL)"

www:
	w3m -o confirm_qq=false "$(APP_URL)"

.PHONY: all venv-setup run run-gunicorn clean distclean image imagerun install-dry install wait uninstall init ping www install
