"""edits：确定性修图的纯函数领域包。

文档变换（document）、像素运算（pixels）、拍平合成（render）三个模块全部是
不碰 fastapi/sqlalchemy 会话的纯函数——毫秒到秒级、可离线、可复现，单测直测。
工具层（app/tools/）负责会话上下文与落库，本包只做运算。
"""
