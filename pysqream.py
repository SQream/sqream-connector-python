
import socket
from struct import pack, unpack
import json

# For interface, see bottom


# Default constants
# Change protocol version with new versions of SQream as necessary
PROTOCOL_VERSION = 4

TCP_IP = '127.0.0.1'
TCP_PORT = 5000
BUFFER_SIZE = 4096
HEADER_LENGTH = 10

# Type conversions for unpack
typeconversion = {"ftInt": "i",
                  "ftUByte": "b",
                  "ftShort": "h",
                  "ftLong": "q",
                  "ftFloat": "f",
                  "ftBool": "?",
                  "ftDouble": "d",
                  "ftDate": "i",
                  "ftDateTime": "q",
                  "ftVarchar": None
                  }

# Class describing column metadata
class SqreamColumn(object):
    def __init__(self):
        self._type_name = None
        self._type_size = None
        self._column_name = None
        self._column_size = None
        self._isTrueVarChar = False
        self._nullable = False
        self._column_data = []

    def set_type_name(self, type_name):
        self._type_name = type_name

    def get_type_name(self):
        return self._type_name

    def set_type_size(self, type_size):
        self._type_size = type_size

    def get_type_size(self):
        return self._type_size

    def set_column_name(self, column_name):
        self._column_name = column_name

    def get_column_name(self):
        return self._column_name

    def set_column_size(self, column_size):
        self._column_size = column_size

    def get_column_size(self):
        return self._column_size

    def set_isTrueVarChar(self,isTrueVarChar):
        self._isTrueVarChar = isTrueVarChar

    def get_isTrueVarChar(self):
        return self._isTrueVarChar

    def set_nullable(self, nullable):
        self._nullable = nullable

    def get_nullable(self):
        return self._nullable

    def set_column_data(self, column_data):
        self._column_data = column_data

    def append_column_data(self, column_data):
        self._column_data += column_data

    def get_column_data(self):
        return self._column_data

# Connection object with sockets and ports and stuff

class SqreamConn(object):
    def __init__(self, username=None, password=None, database=None, host=None, port=None):
        self._socket = None
        self._user = username
        self._password = password
        self._database = database
        self._host = host
        self._port = port

    def set_socket(self, sock):
        self._socket = sock

    def set_user(self, username):
        self._user = username

    def set_password(self, password):
        self._password = password

    def set_database(self, database):
        self._database = database

    def set_host(self, host):
        self._host = host

    def set_port(self, port):
        self._port = port

    def set_socket_parameters(self, host, port):
        self.set_host(host)
        self.set_port(port)

    def set_connection_parameters(self, username, password, database):
        self.set_user(username)
        self.set_password(password)
        self.set_database(database)

    def open_socket(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(13)
        except socket.error as err:
            self._socket = None
            print err

    def close_socket(self):
        if self._socket:
            try:
                self._socket.close()
                self._socket = None
            except(socket.error,AttributeError):
                pass

    def open_connection(self, ip=None, port=None):
        if ip is not None:
            tcp_ip = ip
        else:
            tcp_ip = TCP_IP

        if port is not None:
            tcp_port = port
        else:
            tcp_port = TCP_PORT

        try:
            self._socket.connect((tcp_ip, tcp_port))
        except socket.error as err:
            print err
            if self._socket:
                self.close_connection()
                exit(0)

    def close_connection(self):
        self.close_socket()

    def create_connection(self, ip, port):
        self.open_socket()
        self.open_connection(ip, port)

    def len2ind(self, lens):
        ind = []
        idx = 0
        for i in lens:
            idx += i
            ind.append(idx)
        return ind

    def bytes2vals(self, col_type, column_data):
        unpack_type = typeconversion[col_type]
        if typeconversion[col_type] is not None:
            column_data = map(lambda c: unpack(unpack_type, c)[0], column_data)
        return column_data

    def readcolumnbytes(self, column_bytes):
        chunks = []
        bytes_rcvd = 0
        while bytes_rcvd < column_bytes:
            chunk = self.socket_recv(min(column_bytes - bytes_rcvd, BUFFER_SIZE))
            if chunk == '':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_rcvd += len(chunk)
        column_data = ''.join(chunks)
        return column_data

    def cmd2bytes(self, cmd_str):
        cmd_bytes_1 = bytearray([2])
        cmd_bytes_2 = bytearray([1])
        cmd_bytes_4 = bytearray(cmd_str, 'ascii')
        cmd_bytes_3 = pack('q', len(cmd_bytes_4))
        cmd_bytes = cmd_bytes_1 + cmd_bytes_2 + cmd_bytes_3 + cmd_bytes_4
        return cmd_bytes

    def socket_recv(self, param):
        try:
            data_recv = self._socket.recv(param)
            if '{"error"' in data_recv:
                print repr(data_recv)
                exit(1)
            # TCP says recv will only read 'up to' param bytes, so keep filling buffer
            remainder = param - len(data_recv)
            while remainder > 0:
                data_recv += self._socket.recv(remainder)
                remainder = param - len(data_recv)
        except socket.error as err:
            print err
            self._socket.close()
            self._socket = None
        return data_recv

    def sndcmd2sqream(self, cmd_str):
        cmd_bytes = self.cmd2bytes(cmd_str)
        try:
            self._socket.send(cmd_bytes)
        except socket.error as err:
            print err
            self._socket.close()
            self._socket = None
        data_recv = self.socket_recv(HEADER_LENGTH)
        ver_num = unpack('b', data_recv[0])[0]
        if ver_num is not PROTOCOL_VERSION:
            raise RuntimeError("SQream protocol version mismatch. Expecting " + str(PROTOCOL_VERSION) + ", but got " + str(ver_num) +". Is this a newer/older SQream server?")
        val_len = unpack('q', data_recv[2:])[0]
        data_recv = self.socket_recv(val_len)
        return data_recv

    def connect(self, database, username, password):
        cmd_str = '{"connectDatabase":"' + database + '","password":"' + password + '","username":"' + username + '"}'
        self.sndcmd2sqream(cmd_str)

    def execute(self, query_str):
        err = []
        query_str = query_str.replace('\n', ' ').replace('\r', '')
        cmd_str = '{"prepareStatement":' + '"' + query_str + '","chunkSize":10000}'
        prepareStatement = self.sndcmd2sqream(cmd_str)
        cmd_str = '{"queryTypeOut" : "queryTypeOut"}'
        queryTypeOut = self.sndcmd2sqream(cmd_str)
        queryTypeOut = json.loads(queryTypeOut)

        query_data = list()
        if queryTypeOut["queryTypeNamed"] == []:
            pass
        else:
            for idx, col_type in enumerate(queryTypeOut['queryTypeNamed']):
                sq_col = SqreamColumn()
                sq_col.set_type_name(queryTypeOut['queryTypeNamed'][idx]['type'][0])
                sq_col.set_type_size(queryTypeOut['queryTypeNamed'][idx]['type'][1])
                sq_col.set_column_name(queryTypeOut['queryTypeNamed'][idx]['name'])
                sq_col.set_isTrueVarChar(queryTypeOut['queryTypeNamed'][idx]['isTrueVarChar'])
                sq_col.set_nullable(queryTypeOut['queryTypeNamed'][idx]['nullable'])
                query_data.append(sq_col)
            cmd_str = '{"execute" : "execute"}'
            execute_ = self.sndcmd2sqream(cmd_str)
            # Keep reading while not connection closed
            while True:
                cmd_str = '{"fetch" : "fetch"}'
                fetch = self.sndcmd2sqream(cmd_str)
                fetch = json.loads(fetch)
                rows_num = fetch["rows"]
                if rows_num==0:
                    # No content to read
                    return query_data, err
                # Read to ignore header, which is irrelevant here
                data = self.socket_recv(HEADER_LENGTH)
                col_size = list()
                idx_first = 0
                idx_last = 1
                # Metadata store + how many columns to read ([val], [len,blob], [null,val], [null,len,blob])
                for col_data in query_data:
                    if col_data.get_isTrueVarChar():
                        idx_last += 1
                    if col_data.get_nullable():
                        idx_last += 1
                    col_data.set_column_size(fetch["colSzs"][idx_first:idx_last])
                    idx_first = idx_last
                    idx_last += 1

                    if col_data.get_isTrueVarChar() == False and col_data.get_nullable() == False:
                        column_data = self.readcolumnbytes(col_data.get_column_size()[0])  # , col_data.get_type_size())
                        column_data = [column_data[i:i + col_data.get_type_size()] for i in
                                       range(0, col_data.get_column_size()[0], col_data.get_type_size())]
                        column_data = self.bytes2vals(col_data.get_type_name(), column_data)


                    elif col_data.get_isTrueVarChar() == False and col_data.get_nullable() == True:
                        column_data = self.readcolumnbytes(col_data.get_column_size()[0])
                        is_null = map(lambda c: unpack('b', c)[0], column_data)
                        column_data = self.readcolumnbytes(col_data.get_column_size()[1])  # ,col_data.get_type_size(), None, is_null)
                        column_data = [column_data[i:i + col_data.get_type_size()] for i in
                                       range(0, col_data.get_column_size()[1], col_data.get_type_size())]
                        column_data = self.bytes2vals(col_data.get_type_name(), column_data)
                        column_data = [column_data[idx] if elem == 0 else "\N" for idx, elem in enumerate(is_null)]

                    elif col_data.get_isTrueVarChar() == True and col_data.get_nullable() == False:
                        column_data = self.readcolumnbytes(col_data.get_column_size()[0])
                        column_data = [column_data[i:i + 4] for i in range(0, col_data.get_column_size()[0], 4)]
                        nvarchar_lens = map(lambda c: unpack('i', c)[0], column_data)
                        nvarchar_inds = self.len2ind(nvarchar_lens)
                        column_data = self.readcolumnbytes(col_data.get_column_size()[1])  # , None, nvarchar_inds[:-1])
                        column_data = [column_data[i:j] for i, j in
                                       zip([0] + nvarchar_inds[:-1], nvarchar_inds[:-1] + [None])]

                    elif col_data.get_isTrueVarChar() == True and col_data.get_nullable() == True:
                        column_data = self.readcolumnbytes(col_data.get_column_size()[0])
                        is_null = map(lambda c: unpack('b', c)[0], column_data)

                        column_data = self.readcolumnbytes(col_data.get_column_size()[1])
                        column_data = [column_data[i:i + 4] for i in range(0, col_data.get_column_size()[1], 4)]
                        nvarchar_lens = map(lambda c: unpack('i', c)[0], column_data)
                        nvarchar_inds = self.len2ind(nvarchar_lens)
                        column_data = self.readcolumnbytes(col_data.get_column_size()[2])
                        column_data = [column_data[i:j] if k == 0 else "\N" for i, j, k in
                                       zip([0] + nvarchar_inds[:-1], nvarchar_inds[:-1] + [None], is_null)]

                    col_data.append_column_data(column_data)
            return query_data, err

# This class should be used to create a connection
class connector(object):
    def __init__(self):
        # Store the connection
        self._sc = None
        # Store the columns from the result
        self._cols = None
        self._query = None
    def connect(self,host='127.0.0.1',port=5000,database='master',user='sqream',password='sqream'):
        # No connection yet, create a new one
        if self._sc is None:
            sc = SqreamConn()
            sc.create_connection(host,port)
            sc.connect(database,user,password)
            self._sc = sc
            return self._sc
        else:
            raise RuntimeError("Connection already exists. You must close the current connection before creating a new one")
    def last_query(self):
        return self._query
    def last_cols(self):
        return self._cols
    def close(self):
        # Close existing connection
        if self._sc is None:
            return
        else:
            self._sc.close_socket()
    def query(self,query=None):
        if query is None:
            raise RuntimeError("Query is empty")
        else:
            self._query = query
            try:
                columns,err = self._sc.execute(query)
                if err != []:
                    raise RuntimeError(err)
                else:
                    self._cols = columns
                    return self._cols
            except:
                print "Unexpected error"
                raise
    def cols_data(self,cols=None):
        if cols==None:
            cols = self._cols
        return map(lambda c: c.get_column_data(),cols)
    def cols_names(self,cols=None):
        if cols==None:
            cols = self._cols
        return map(lambda c: c.get_column_name(),cols)
    def cols_types(self,cols=None):
        if cols==None:
            cols = self._cols
        return map(lambda c: c.get_type_name(),cols)

    def cols_to_rows(self,cols=None):
        # Transpose the columns into rows
        if cols==None:
            cols = self._cols
        cursor = self.cols_data(cols)
        return map(list, zip(*cursor))


if __name__ == "__main__":
    sc = connector()
    sc.connect(host='192.168.0.161')
    cols = sc.query("SELECT * FROM foo")
    print sc.cols_names()
    print sc.cols_types()
    print sc.cols_to_rows()