Commands To Run

docker-compose up

./init-scripts/setup.sh
 
curl -X POST http://localhost:4566/restapis/quf1smtfi4/dev/_user_request_/upload \
  -H "Content-Type: application/json" \
  -d '{
    "image":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+X4kAAAAASUVORK5CYII=",
    "metadata":{
      "user_id":"user2",
      "content_type": "image/png",
      "tags":["sun"],
      "description":"sunset"
    }
  }'

curl http://localhost:4566/restapis/quf1smtfi4/dev/_user_request_/images
 
curl http://localhost:4566/restapis/quf1smtfi4/dev/_user_request_/images/a2012ba6-df73-4a4b-aab5-85e289f19a08
 
curl "http://localhost:4566/restapis/quf1smtfi4/dev/_user_request_/images?user_id=user1"
curl "http://localhost:4566/restapis/quf1smtfi4/dev/_user_request_/images?tag=nature"   


curl -X DELETE http://localhost:4566/restapis/quf1smtfi4/dev/_user_request_/images/a2012ba6-df73-4a4b-aab5-85e289f19a0f
 
make localstack-down