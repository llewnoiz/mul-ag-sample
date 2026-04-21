#!make
# macros
region      = us-east-1
stack       = electrify-$(region)
bucket      = dat403-workshop-$(region)
template    = ../static/electrify.yml
modules     = ../modules
assets      = ../assets

# Create bucket if it doesn't exist with ACL support
ensure-bucket:
	@if ! aws s3api head-bucket --bucket $(bucket) 2>/dev/null; then \
		echo "Creating bucket $(bucket) in $(region)..."; \
		if [ "$(region)" = "us-east-1" ]; then \
			aws s3api create-bucket --bucket $(bucket) --region $(region); \
		else \
			aws s3api create-bucket --bucket $(bucket) --region $(region) --create-bucket-configuration LocationConstraint=$(region); \
		fi; \
		aws s3api put-public-access-block --bucket $(bucket) --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=true,RestrictPublicBuckets=true"; \
		aws s3api put-bucket-ownership-controls --bucket $(bucket) --ownership-controls "Rules=[{ObjectOwnership=BucketOwnerPreferred}]"; \
		echo "Bucket $(bucket) created."; \
	else \
		echo "Using existing bucket $(bucket)."; \
	fi

# rules
all: infra-deploy

## -------------------------------------------------------
## Package assets (zip api, webui, modules) for deployment
## -------------------------------------------------------
zip-assets:
	rm -f $(assets)/app.zip $(assets)/webui.zip $(assets)/modules.zip $(assets)/supportscripts.zip
	# Copy modules to temp dir, strip solutions, then zip from there
	rm -rf $(assets)/_modules_tmp
	cp -r $(modules)/. $(assets)/_modules_tmp
	../prepare_challenges.sh $(assets)/_modules_tmp
	cd $(assets)/_modules_tmp && zip -r $(CURDIR)/$(assets)/modules.zip . -x "*__pycache__*" -x "*.pyc" -x "*.zip"
	rm -rf $(assets)/_modules_tmp
	cd ../api && zip $(CURDIR)/$(assets)/app.zip app.py
	cd . && zip -r $(assets)/webui.zip . -x "node_modules/*" -x "dist/*" -x "temp/*" -x ".env"
	cd .. && zip $(CURDIR)/$(assets)/supportscripts.zip init_schema.sql policy.md populate.py pyproject.toml test_strands_full.sh test_langgraph_full.sh

## -------------------------------------------------------
## Upload assets to your S3 bucket for CFN deployment
## -------------------------------------------------------
upload-assets:
	aws s3 cp $(assets)/app.zip s3://$(bucket)/api/app.zip --acl public-read
	aws s3 cp $(assets)/webui.zip s3://$(bucket)/webui.zip --acl public-read
	aws s3 cp $(assets)/modules.zip s3://$(bucket)/modules.zip --acl public-read
	aws s3 cp $(assets)/supportscripts.zip s3://$(bucket)/supportscripts.zip --acl public-read

## -------------------------------------------------------
## Deploy infrastructure to your test AWS account
## Creates a local.yml from the WS template with bucket refs swapped
## -------------------------------------------------------
infra-deploy: ensure-bucket zip-assets upload-assets
	if [ -d ./temp ]; then rm -rf ./temp; fi && mkdir ./temp
	sed 's|Bucket: !Ref MyAssetsBucketName|Bucket: $(bucket)|g; \
		s|Key: !Sub.*api/app.zip.*|Key: api/app.zip|g; \
		s|https://rivassets.s3.us-east-1.amazonaws.com/dat403riv2025|https://$(bucket).s3.$(region).amazonaws.com|g' $(template) > ./temp/local.yml
	aws cloudformation package --template-file ./temp/local.yml --s3-bucket "$(bucket)" --output-template-file ./temp/packaged.yml --region "$(region)"
	aws cloudformation deploy --template-file ./temp/packaged.yml --stack-name "$(stack)" --s3-bucket "$(bucket)" --capabilities CAPABILITY_NAMED_IAM --region "$(region)"

## -------------------------------------------------------
## Install npm dependencies
## -------------------------------------------------------
app-provision:
	npm install

## -------------------------------------------------------
## Build the web app (pulls env from deployed stack outputs)
## -------------------------------------------------------
app-build:
	echo VITE_AWS_REGION=$(region) > .env
	echo VITE_API_ENDPOINT=https://$$(aws cloudformation describe-stacks --stack-name "$(stack)" --region "$(region)" --query "Stacks[0].Outputs[?OutputKey == 'ApiEndpoint'].OutputValue" --output text) >> .env
	echo VITE_IDENTITY_POOL=$$(aws cloudformation describe-stacks --stack-name "$(stack)" --region "$(region)" --query "Stacks[0].Outputs[?OutputKey == 'CognitoIdP'].OutputValue" --output text) >> .env
	echo VITE_COGNITO_POOL=$$(aws cloudformation describe-stacks --stack-name "$(stack)" --region "$(region)" --query "Stacks[0].Outputs[?OutputKey == 'CognitoPool'].OutputValue" --output text) >> .env
	echo VITE_COGNITO_CLIENT=$$(aws cloudformation describe-stacks --stack-name "$(stack)" --region "$(region)" --query "Stacks[0].Outputs[?OutputKey == 'CognitoClient'].OutputValue" --output text) >> .env
	echo VITE_COGNITO_DOMAIN=$$(aws cloudformation describe-stacks --stack-name "$(stack)" --region "$(region)" --query "Stacks[0].Outputs[?OutputKey == 'CognitoDomain'].OutputValue" --output text) >> .env
	echo VITE_AGENTCORE_URL=$(runtime) >> .env
	npm install
	npm run build
	BUCKET=$$(aws cloudformation describe-stacks --stack-name "$(stack)" --region "$(region)" --query "Stacks[0].Outputs[?OutputKey == 'ContentBucket'].OutputValue" --output text) && aws s3 cp ./dist "s3://$$BUCKET/website/" --recursive

## -------------------------------------------------------
## Deploy built web app to the stack's content bucket
## -------------------------------------------------------
deploy:
	BUCKET=$$(aws cloudformation describe-stacks --stack-name "$(stack)" --region "$(region)" --query "Stacks[0].Outputs[?OutputKey == 'ContentBucket'].OutputValue" --output text) && \
	aws s3 cp ./dist "s3://$$BUCKET/website/" --recursive

## -------------------------------------------------------
## Prepare assets for Workshop Studio
## Packages zips, generates electrify-public.yml, uploads to rivassets S3
## -------------------------------------------------------
ws-prep: zip-assets
	# Lambda CodeUri needs api/app.zip in the assets bucket
	rm -rf $(assets)/api
	mkdir -p $(assets)/api
	cp $(assets)/app.zip $(assets)/api/app.zip
	# Generate public CFN template
	python3 ../static/convert_to_public.py $(template) ../static/electrify-public.yml
	# Upload assets to rivassets S3 for public/non-WS access
	aws s3 cp $(assets)/app.zip s3://rivassets/dat403riv2025/ --acl public-read
	aws s3 cp $(assets)/webui.zip s3://rivassets/dat403riv2025/ --acl public-read
	aws s3 cp $(assets)/modules.zip s3://rivassets/dat403riv2025/ --acl public-read
	aws s3 cp $(assets)/supportscripts.zip s3://rivassets/dat403riv2025/ --acl public-read
	aws s3 cp ../static/electrify-public.yml s3://rivassets/dat403riv2025/ --acl public-read

## -------------------------------------------------------
## Clean build artifacts
## -------------------------------------------------------
clean:
	rm -rf ./dist ./temp .env $(assets)/app.zip $(assets)/webui.zip $(assets)/modules.zip $(assets)/supportscripts.zip $(assets)/api

.PHONY: all zip-assets upload-assets infra-deploy app-provision app-build deploy ws-prep clean ensure-bucket
