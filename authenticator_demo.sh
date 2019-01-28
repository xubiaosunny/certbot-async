#!/bin/sh
echo 'The domain being authenticated: '$CERTBOT_DOMAIN
echo 'The validation string (HTTP-01 and DNS-01 only): '$CERTBOT_VALIDATION
echo ' Resource name part of the HTTP-01 challenge (HTTP-01 only): '$CERTBOT_TOKEN

/bin/sleep 20
