from flask import Flask, request, redirect, url_for, render_template, flash, send_file
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import extract
import pandas as pd
from io import BytesIO
import os


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 设置你的 secret key
app.config['UPLOAD_FOLDER'] = './static/uploads'  # 设置上传文件的保存路径
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orders.db'  # 数据库路径
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 禁用不必要的警告

db = SQLAlchemy(app)  # 将 SQLAlchemy 直接与 Flask 应用关联

# 确保文件上传目录存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# 定义订单模型
class Order(db.Model):
    __tablename__ = 'order'  # 明确指定表名
    id = db.Column(db.Integer, primary_key=True)
    order_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_settled = db.Column(db.Boolean, default=False)
    boss_name = db.Column(db.String(100))
    play_name = db.Column(db.String(100))
    game_type = db.Column(db.String(100))
    price = db.Column(db.Float)
    play_time = db.Column(db.Integer)
    total_price = db.Column(db.Float)
    commission = db.Column(db.Float)
    final_amount = db.Column(db.Float)
    sweet_name = db.Column(db.String(100))  # 甜蜜称呼
    is_paid = db.Column(db.Boolean, default=False)
    remarks = db.Column(db.String(255), default='无')  # 添加备注字段

# 进入数据库会话
with app.app_context():
    db.create_all()  # 重新创建表

@app.route('/')
def index():
    orders = Order.query.all()
    total_price = sum(order.total_price for order in orders)
    total_commission = round(sum(order.commission for order in orders), 2)
    total_final_amount = round(sum(order.final_amount for order in orders), 2)
    total_orders = len(orders)

    return render_template('index.html', orders=orders, total_price=total_price, 
                           total_commission=total_commission, total_final_amount=total_final_amount, 
                           total_orders=total_orders)

# 订单详情路由
@app.route('/order/<int:order_id>')
def order_details(order_id):
    order = Order.query.get(order_id)
    
    if order is None:
        flash('订单未找到', 'danger')
        return redirect(url_for('index'))
    
    return render_template('order_details.html', order=order)

@app.route('/new_order', methods=['GET', 'POST'])
def new_order():
    if request.method == 'POST':
        # 获取表单数据
        boss_name = request.form.get('boss_name')
        play_name = request.form.get('play_name')
        game_type = request.form.get('game_type')
        price = request.form.get('price')
        play_time = request.form.get('play_time')
        sweet_name = '有' if 'sweet_name' in request.form else '无'  # 根据是否勾选设置值
        win_image = request.files.get('win_image')
        other_image = request.files.get('other_image')
        remarks = request.form.get('remarks')  # 获取备注

        # 校验必填字段
        if not boss_name or not play_name or not game_type or not price or not play_time:
            flash('请完整填写所有必填字段！', 'danger')
            return redirect(url_for('new_order'))

        # 处理文件上传
        if win_image:
            win_image_filename = secure_filename(win_image.filename)
            win_image.save(os.path.join(app.config['UPLOAD_FOLDER'], win_image_filename))
        
        if other_image:
            other_image_filename = secure_filename(other_image.filename)
            other_image.save(os.path.join(app.config['UPLOAD_FOLDER'], other_image_filename))

        # 添加数据到数据库
        new_order = Order(
            order_time=datetime.now(),  # 使用 datetime 对象
            is_settled=False,
            boss_name=boss_name,
            play_name=play_name,
            game_type=game_type,
            price=float(price),
            play_time=int(play_time),
            total_price=float(price) * int(play_time),
            commission=float(price) * int(play_time) * 0.1,
            final_amount=float(price) * int(play_time) * 0.9,
            sweet_name=sweet_name,
            is_paid=False,
            remarks=remarks  # 保存备注
        )
        db.session.add(new_order)
        db.session.commit()

        flash('订单提交成功！', 'success')
        return redirect(url_for('index'))

    return render_template('new_order.html')

@app.route('/update_settlement_status/<int:order_id>', methods=['POST'])
def update_settlement_status(order_id):
    # 更新结算状态
    order = Order.query.get(order_id)
    if order:
        settlement_status = request.form.get('settlement_status')
        order.is_settled = settlement_status == '已结'
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/update_payment_status/<int:order_id>', methods=['POST'])
def update_payment_status(order_id):
    # 更新付款状态
    order = Order.query.get(order_id)
    if order:
        payment_status = request.form.get('payment_status')
        order.is_paid = payment_status == '已收'
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    # 删除订单
    order = Order.query.get(order_id)
    if order:
        db.session.delete(order)
        db.session.commit()
        flash('订单已删除', 'success')
    else:
        flash('订单未找到', 'danger')
    
    return redirect(url_for('index'))

@app.route('/export_report/<string:report_type>')
def export_report(report_type):
    if report_type == 'all':
        # 从数据库中查询所有订单
        orders = Order.query.all()
        
        # 将查询结果转换为字典列表以便构造 DataFrame
        order_list = []
        for order in orders:
            order_dict = {
                'ID': order.id,
                'Order Time': order.order_time,
                'Is Settled': '已结' if order.is_settled else '未结',
                'Boss Name': order.boss_name,
                'Play Name': order.play_name,
                'Game Type': order.game_type,
                'Price': order.price,
                'Play Time': order.play_time,
                'Total Price': order.total_price,
                'Commission': order.commission,
                'Final Amount': order.final_amount,
                'Sweet Name': order.sweet_name,
                'Is Paid': '已收' if order.is_paid else '未收',
                'Remarks': order.remarks
            }
            order_list.append(order_dict)
        
        # 使用 Pandas 生成 DataFrame
        df = pd.DataFrame(order_list)

        # 生成 Excel 文件
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Orders', index=False)
        output.seek(0)

        # 返回生成的 Excel 文件
        return send_file(output, download_name='all_orders_report.xlsx', as_attachment=True)
    
@app.route('/export_report_by_month/<string:month>')
def export_report_by_month(month):
    # 将接收到的月份解析为年和月
    year, month = month.split('-')
    
    # 查询该月份内的所有订单
    orders = Order.query.filter(db.extract('year', Order.order_time) == year,
                                db.extract('month', Order.order_time) == month).all()

    # 将查询结果转换为字典列表
    order_list = []
    for order in orders:
        order_dict = {
            'ID': order.id,
            'Order Time': order.order_time,
            'Is Settled': '已结' if order.is_settled else '未结',
            'Boss Name': order.boss_name,
            'Play Name': order.play_name,
            'Game Type': order.game_type,
            'Price': order.price,
            'Play Time': order.play_time,
            'Total Price': order.total_price,
            'Commission': order.commission,
            'Final Amount': order.final_amount,
            'Sweet Name': order.sweet_name,
            'Is Paid': '已收' if order.is_paid else '未收',
            'Remarks': order.remarks
        }
        order_list.append(order_dict)
    
    # 使用 Pandas 生成 DataFrame
    df = pd.DataFrame(order_list)

    # 生成 Excel 文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=f'{year}-{month} Orders', index=False)
    output.seek(0)

    # 返回生成的 Excel 文件
    return send_file(output, download_name=f'{year}-{month}_orders_report.xlsx', as_attachment=True)
    
if __name__ == '__main__':
    app.run(port=5002, debug=True)