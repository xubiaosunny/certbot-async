#!/bin/sh

curl -X PUT "https://api.cloudflare.com/client/v4/zones/<zone_identifier>/dns_records/<identifier>" \
    -H "X-Auth-Email: user@example.com" \
    -H "X-Auth-Key: <user_key>" \
    -H "Content-Type: application/json" \
    --data '{"type":"TXT","name":"_acme-challenge","content":"${CERTBOT_VALIDATION}","ttl":1,"priority":10,"proxied":false}'

/bin/sleep 30
