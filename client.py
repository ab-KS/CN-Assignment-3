import socket
import threading
import time
import queue
import random

# Client configuration
SERVER_IP = 'localhost'
CLIENT_IP = 'localhost'
SERVER_PORT = 12000
CLIENT_PORT = 5001
TOTAL_PACKETS = 100  # Number of packets to send

WINDOW_SIZE = 7 #This is the Transmit window size

T1 = 0.001
T2 = 0.01
T3 = 0.01
T4 = 0.1

DROP_PROB = 0.1

ack_message_count = 0
ack_message_lock = threading.Lock()

outgoing_queue = queue.Queue()

window = [] #using a list to simulate window while making sure that its size remains equal to window_size

window_seq_number = 0

lock = threading.Lock()

timeout = 1

timeout_timer = threading.Timer(timeout, lambda:reset_seq_number())   #lambda functions are shortlived functions and it enables us to use the function defined later

# Create a client socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_socket.bind((CLIENT_IP, CLIENT_PORT))

# Send the ready signal to the server
def send_ready_signal():
    message = "READY".encode()
    client_socket.sendto(message, (SERVER_IP, SERVER_PORT))
    print("Client sent ready signal to server.")


#This function is used if we need to retransmit due to timeout
def reset_seq_number():
    global window_seq_number
    lock.acquire()
    window_seq_number = 0
    if(len(window)>0):
        print(f"Retransmitting Packets {window[0]} to {window[len(window)-1]}\n")
    lock.release()

def send_packets(socket,t3,t4):
    """for i in range(TOTAL_PACKETS):
        message = f"DL_Entity_1, Client-Packet-{i+1} - SeqNum {i}".encode()
        client_socket.sendto(message, (SERVER_IP, SERVER_PORT))
        print(f"Message Sent: {message.decode()}")
        time.sleep(1)  # Simulate some delay between packets"""
    global window_seq_number
    while True:
        if (len(window)>0 and window_seq_number<7 and window_seq_number<len(window)):
            message = f"DL_Entity_1, Client-Packet-{window[window_seq_number-1]+1} - SeqNum {window[window_seq_number-1]}".encode()
            #print(message)
            #Propogation Delay
            print(f"Message Sent: {message}\n")
            wait_time = random.uniform(t3, t4)
            time.sleep(wait_time)
            client_socket.sendto(message, (SERVER_IP,SERVER_PORT))
            if(window_seq_number==0):
                timeout_timer = threading.Timer(timeout, lambda:reset_seq_number())
                timeout_timer.start()
            window_seq_number+=1

def receive_acks(socket):
    #global ack_message_count
    global window_seq_number
    while True:  # Loop until all packets are acknowledged
        try:
            packet, addr = client_socket.recvfrom(1024)
            if(packet.decode().startswith("Ack")):
                
                
                ack_message = packet.decode()
                ack_number = ack_message.split(": ")[1]
                #print(ack_number)
                if(len(window) and int(ack_number)!=window[0]):
                    continue
                timeout_timer.cancel()
                
                #Sliding the window forward if the Ack is received
                lock.acquire()
                if(len(window) > 0):
                    print(f"Ack Received: {ack_message}")
                    window.pop(0)
                    window_seq_number-=1
                    print(window)
                    print("\n")
                    
                lock.release()
                #The window slides automatically when the slide_window function is continuously running on another thread
                #slide_window()
            
            else:
                message, seq_num = packet.decode().rsplit(" - SeqNum ", 1)
                seq_num = int(seq_num)
                print(f"Message Received: {message} - SeqNum {seq_num}\n")
                
                # Send an ACK for each received packet
                ack_message = f"Ack: {seq_num}".encode()

                #simulating packet drop with a drop rate of 30%
                random_number = random.random()
                
                if(random_number<DROP_PROB):
                    continue

                client_socket.sendto(ack_message, addr)
                print(f"Ack sent: {ack_message.decode()}\n")
            
            """with ack_message_lock:
                ack_message_count += 1"""
        
        except ConnectionResetError as e:
            print(f"Connection was reset by the Client: {e}")
            break  # Exit the loop if the connection is closed unexpectedly


def packet_generator(packet_count, t1, t2, queue):
    for i in range(packet_count):
        packet = f"Client-Packet-{i+1}"
        queue.put(i+1)
        print(f"Generated and added {packet} to the outgoing queue\n")
        wait_time = random.uniform(t1, t2)
        #print(f"Next packet will be generated in {wait_time:.2f} seconds")
        time.sleep(wait_time)

def slide_window(outgoing_queue,window):
    while True:
        if(not outgoing_queue.empty() and len(window)<7):
            lock.acquire()
            print("Adding to the Window From the Outgoing Queue:")
            window.append(outgoing_queue.get())
            print(window)
            print("\n")
            lock.release()

# Receive packets and send ACKs
# Run send_packets and receive_acks functions in separate threads
sliding_thread = threading.Thread(target = slide_window, args=(outgoing_queue,window))
generator_thread = threading.Thread(target = packet_generator, args=(TOTAL_PACKETS, T1, T2, outgoing_queue))
send_ready_signal_thread = threading.Thread(target=send_ready_signal)
send_thread = threading.Thread(target=send_packets, args=(client_socket,T3,T4))
receive_thread = threading.Thread(target=receive_acks, args=(client_socket,))

send_ready_signal_thread.start()
send_ready_signal_thread.join()  # Ensure client sends ready signal first

# Start the threads
generator_thread.start()
sliding_thread.start()
receive_thread.start()
send_thread.start()

# Join the threads to wait for them to finish (optional, depends on your use case)
send_thread.join()
receive_thread.join()
generator_thread.join()
sliding_thread.join()
client_socket.close()