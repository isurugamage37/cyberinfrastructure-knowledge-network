import json
import random
import threading
import panel as pn
from confluent_kafka import Consumer
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource
import os

pn.extension(sizing_mode="stretch_width")
CKN_KAFKA_BROKER = os.getenv('CKN_KAFKA_BROKER', 'localhost:9092')
DASHBOARD_GROUP_ID = os.getenv('DASHBOARD_GROUP_ID', 'ckn-analytics-dashboard')
CKN_KAFKA_OFFSET = os.getenv('CKN_KAFKA_OFFSET', 'earliest')
ORACLE_EVENTS_TOPIC = os.getenv('ORACLE_EVENTS_TOPIC', 'oracle-events')
ORACLE_ALERTS_TOPIC = os.getenv('ORACLE_ALERTS_TOPIC', 'oracle-alerts')

# Create a lock for thread-safe updates
event_lock = threading.Lock()

def create_consumer():
    return Consumer({
        'bootstrap.servers': CKN_KAFKA_BROKER,
        'group.id': DASHBOARD_GROUP_ID,
        'auto.offset.reset': CKN_KAFKA_OFFSET
    })

alert_stream = pn.pane.JSON()
event_dict = {'time': [], 'probability': []}
source = ColumnDataSource(data=event_dict)

# General function to consume messages from Kafka
def consume_topic(topic_name, update_function):
    consumer = create_consumer()
    consumer.subscribe([topic_name])


source = ColumnDataSource(data={'time': [], 'probability': []})
plot = figure(title="Score Probability Over Time", x_axis_type='datetime', height=330, sizing_mode='stretch_width')
plot.line(x='time', y='probability', source=source, line_width=2)
plot.xaxis.axis_label = 'Time'
plot.yaxis.axis_label = 'Score Probability'

# Function to consume messages from Kafka
def consume_messages():
    config = {
        'bootstrap.servers': CKN_KAFKA_BROKER,
        'group.id': DASHBOARD_GROUP_ID,
        'auto.offset.reset': CKN_KAFKA_OFFSET
    }

    consumer = Consumer(config)
    consumer.subscribe([ORACLE_EVENTS_TOPIC])

    while True:
        msg = consumer.poll(1.0)
        if msg is not None and not msg.error():
            event = json.loads(msg.value().decode('utf-8')) if msg.value() is not None else None
            if event:
                pn.state.execute(lambda: update_function(event))

def update_alert_stream(event):
    alert_stream.object = json.dumps(event, indent=2)

def update_event_stream(event):
    with event_lock:
        timestamp_str = event.get("image_receiving_timestamp")
        if timestamp_str:
            timestamp = parser.isoparse(timestamp_str)
            event_dict['time'].append(timestamp)
            event_dict['probability'].append(event["probability"])

def periodic_callback():
    with event_lock:
        if event_dict['time'] and event_dict['probability']:
            source.stream({'time': [event_dict['time'][-1]], 'probability': [event_dict['probability'][-1]]})

# Start Kafka consumers in separate threads
threading.Thread(target=consume_topic, args=("oracle-alerts", update_alert_stream), daemon=True).start()
threading.Thread(target=consume_topic, args=("oracle-events", update_event_stream), daemon=True).start()

alerts_card = pn.Card(alert_stream, title="Alerts")

event_plot_figure = figure(title="Score Probability Over Time", x_axis_type='datetime', height=350, sizing_mode="stretch_width")
event_plot_figure.line(x='time', y='probability', source=source, line_width=2)
event_plot_figure.xaxis.axis_label = 'Time'
event_plot_figure.yaxis.axis_label = 'Score Probability'
event_plot = pn.pane.Bokeh(event_plot_figure)

# Create the FastListTemplate
template = pn.template.FastListTemplate(
    title="CKN Analytics Dashboard",
    main=[alerts_card, event_plot],
    logo="https://www.iu.edu/images/brand/brand-expression/iu-trident-promo.jpg",
    accent="#990000"
)

# Schedule the periodic callback for updating the plot
pn.state.add_periodic_callback(periodic_callback, period=1000)  # Update every second

# Serve the template
template.servable()
