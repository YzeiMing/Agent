FastAPI本身是Web框架，不直接处理底层的HTTP协议解析。当遇到：

File参数

Form参数（特别是与文件一起使用时）

FastAPI会调用 python-multipart来解析HTTP请求体中的multipart数据。
python-multipart