Commands To Run

docker-compose up

./init-scripts/setup.sh
 
curl -X POST http://localhost:4566/restapis/qltxkf6dyl/dev/_user_request_/upload \
  -H "Content-Type: application/json" \
  -d '{
    "image":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+X4kAAAAASUVORK5CYII=",
    "metadata":{
      "user_id":"user4",
      "content_type": "image/png",
      "tags":["nithu"],
      "description":"sunset"
    }
  }'

 curl http://localhost:4566/restapis/qltxkf6dyl/dev/_user_request_/images
 
 curl http://localhost:4566/restapis/qltxkf6dyl/dev/_user_request_/images/e2acc802-8a2d-4e94-a11c-c56215393b68
 
curl "http://localhost:4566/restapis/qltxkf6dyl/dev/_user_request_/images?user_id=user1"
curl "http://localhost:4566/restapis/qltxkf6dyl/dev/_user_request_/images?tag=nature"   


 curl -X DELETE http://localhost:4566/restapis/qltxkf6dyl/dev/_user_request_/images/535a4e38-cde7-42de-9b99-7a58dce2e08c
 
make localstack-down