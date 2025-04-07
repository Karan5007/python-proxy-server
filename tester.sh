# curl http://localhost:8888/www.example.org &
curl http://localhost:8888/www.cs.toronto.edu/~ylzhang/ &
curl http://localhost:8888/www.cs.toronto.edu/~arnold/ &
wait

sleep 11

# curl http://localhost:8888/www.example.org &
curl http://localhost:8888/www.cs.toronto.edu/~ylzhang/ &
curl http://localhost:8888/www.cs.toronto.edu/~arnold/ &
wait

sleep 1
# curl http://localhost:8888/www.example.org &
curl http://localhost:8888/www.cs.toronto.edu/~ylzhang/ &
curl http://localhost:8888/www.cs.toronto.edu/~arnold/ &
wait
