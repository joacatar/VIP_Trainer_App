from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'your_secret_key'


def get_selected_checkboxes(feedback, name):
    selected_values = feedback.getlist(name)
    other_text = feedback.get(name + 'OtherText', '').strip()
    if other_text:
        selected_values.append(other_text)
    return ''.join(selected_values) or 'Up to Protocol'


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['order_number'] = request.form['orderNumber']
        return redirect(url_for('page2'))
    return render_template('page1.html')


@app.route('/page1', methods=['GET', 'POST'])
def page1():
    if request.method == 'POST':
        session['order_number'] = request.form['orderNumber']
        return redirect(url_for('page2'))
    return render_template('page1.html')


@app.route('/page2', methods=['GET', 'POST'])
def page2():
    if request.method == 'POST':
        feedback = request.form
        mapped_feedback = {
            "Scan comments": get_selected_checkboxes(feedback, 'q1C'),
            "Rider form comments": get_selected_checkboxes(feedback, 'q2C'),
            "Segmentation comments": get_selected_checkboxes(feedback, 'q3C'),
            "Scapula landmarking comments": get_selected_checkboxes(feedback, 'q4C'),
            "Glenoid landmarking comments": get_selected_checkboxes(feedback, 'q5C'),
            "Humeral landmark comments": get_selected_checkboxes(feedback, 'q6C'),
            "Humeral implant comments": get_selected_checkboxes(feedback, 'q7C'),
            "Glenoid implant comments": get_selected_checkboxes(feedback, 'q8C')
        }
        session['feedback'] = mapped_feedback
        # session['feedback'] = feedback
        session['name'] = request.form['name']
        return redirect(url_for('page3'))
    return render_template('page2.html')


@app.route('/page3')
def page3():
    order_number = session.get('order_number')
    feedback = session.get('feedback', {})
    name = session.get('name')
    return render_template('page3.html', feedback=feedback, order_number=order_number, name=name)


@app.route('/traineess')
def individuals():
    traineess = ['Kate', 'Shahrenna']  # Example list of traineess
    return render_template('traineess.html', traineess=traineess)


@app.route('/traineess/<name>')
def individual_sets(name):
    sets = {
        'Justin': ['Set 1', 'Set 2'],
        'Cindy': ['Set 1'],
        'Emma': ['Set 1', 'Set 2', 'Set 3']
    }
    individual_sets = sets.get(name, [])
    return render_template('sets.html', name=name, sets=individual_sets)


@app.route('/traineess/<name>/<set_name>')
def set_cases(name, set_name):
    cases = {
        'Set 1': ['Case 1', 'Case 2', 'Case 3', 'Case 4', 'Case 5', 'Case 6', 'Case 7', 'Case 8', 'Case 9', 'Case 10', 'Case 11', 'Case 12', 'Case 13', 'Case 14', 'Case 15', 'Case 16'],
        'Set 2': ['Case 1', 'Case 2', 'Case 3', 'Case 4', 'Case 5', 'Case 6', 'Case 7', 'Case 8', 'Case 9', 'Case 10', 'Case 11', 'Case 12', 'Case 13', 'Case 14', 'Case 15', 'Case 16']
    }
    set_cases = cases.get(set_name, [])
    return render_template('cases.html', name=name, set_name=set_name, cases=set_cases)



if __name__ == '__main__':
    app.run(debug=True)