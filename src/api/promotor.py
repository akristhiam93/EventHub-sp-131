from flask import Flask, request, jsonify, url_for, Blueprint
from api.models import db, Promotor, Event, EventPromotor, SavedEvent, EventCategory, EventAssistUser, GroupEvent, Category, Comment, User, Chat, Message
from sqlalchemy import select
from datetime import datetime, timezone
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, verify_jwt_in_request
from api.security import current_account_id, current_role, hash_password, issue_token, verify_password

promotor = Blueprint('promotor', __name__,)


@promotor.before_request
def require_promotor_role():
    if request.method == "OPTIONS":
        return None
    if request.endpoint in {"promotor.login_promotor", "promotor.signUp_promotor"}:
        return None
    verify_jwt_in_request()
    if current_role() != "promotor":
        return jsonify({"message": "Se requiere una cuenta de promotor"}), 403

# // Promotor Auth


@promotor.route('/login', methods=['POST'])
def login_promotor():
    email = request.json.get("email", None)
    password = request.json.get("password", None)

    promotors = db.session.execute(select(Promotor)).scalars().all()

    if email == None or password == None:
        return jsonify({"msg": "Bad email or password"}), 401
    for promot in promotors:
        if email == promot.email and verify_password(promot.password, password):
            if not promot.password.startswith(("pbkdf2:", "scrypt:")):
                promot.password = hash_password(password)
                db.session.commit()
            access_token = issue_token(promot, "promotor")
            return jsonify(access_token=access_token), 200

    return jsonify({"msg": "Bad email or password"}), 401


@promotor.route('/private', methods=['GET'])
@jwt_required()
def private_promotor():
    if current_role() != "promotor":
        return jsonify({"msg": "No tienes permisos para esta ruta"}), 403
    promot = db.session.get(Promotor, current_account_id())
    if promot is None:
        return jsonify({"msg": "Promotor no encontrado"}), 404

    return jsonify({
        "msg": "Token valid",
        "promotor": promot.serialize()
    }), 200


@promotor.route('/sign-in', methods=['POST'])
def signUp_promotor():
    promotors = db.session.execute(select(Promotor)).scalars().all()
    body = request.json
    for promotor in promotors:
        if promotor.email == body["email"]:
            return {"msg": "invalid email"}, 409
        if promotor.name == body["name"]:
            return {"msg": "invalid name"}, 409
        if promotor.phone == body["phone"]:
            return {"msg": "invalid phone"}, 409
        if promotor.web_page == body["web_page"]:
            return {"msg": "invalid web page url"}, 409
    body["password"] = hash_password(body["password"])
    promotor = Promotor(**body, verified_org=False)
    db.session.add(promotor)
    db.session.commit()

    return jsonify({
        "msg": "Promotor created succesfully",
        "promotor": promotor.email
    }), 201

# crear Eventos para X promotor


@promotor.route("/<int:promotor_id>/events", methods=["GET"])
@jwt_required()
def get_events(promotor_id):
    promotor = db.session.get(Promotor, promotor_id)
    promotorRelation = db.session.execute(select(EventPromotor).where(
        EventPromotor.promotor_id == promotor_id)).scalars().all()
    events = []
    for relation in promotorRelation:
        events.append(db.session.get(Event, relation.event_id))

    for event in events:
        if event is None:
            return jsonify({"message": "No events found"}), 404

    return jsonify({
        "message": f"{len(events)} where found for promotor {promotor.name}",
        "relations": list(map(lambda relation: relation.serialize(), promotorRelation)),
        "events": list(map(lambda event: event.serialize(), events))
    }), 200


@promotor.route("/<int:promotor_id>/events/<int:event_id>", methods=["GET"])
# @jwt_required()
def get_event_by_id(promotor_id, event_id):
    event = db.session.get(Event, event_id)
    promotor = db.session.get(Promotor, promotor_id)

    if event is None:
        return jsonify({"message": "Evento no encontrado"}), 404

    return jsonify({
        "message": f"Event with name {event.name} of owner {promotor.name}",
        "promotor": promotor.serialize(),
        "event": event.serialize()
    }), 200


@promotor.route("/<int:promotor_id>/events", methods=["POST"])
@jwt_required()
def create_event(promotor_id):
    body = request.get_json(silent=True)
    promotor = db.session.get(Promotor, promotor_id)

    if current_account_id() != promotor_id:
        return jsonify({"message": "No tienes permiso para crear eventos para este promotor"}), 403

    if body is None:
        return jsonify({"message": "Debes enviar un JSON válido"}), 400

    name = body.get("name")
    location = body.get("location")
    lat = body.get("lat")
    lng = body.get("lng")
    description = body.get("description")
    date_event_str = body.get("date_event")
    capacity = body.get("capacity")
    media = body.get("media")

    # VALIDACIONES
    if not name or not date_event_str:
        return jsonify({"message": "Name y date_event son obligatorios"}), 400

    # Validar fecha
    try:
        date_event = datetime.fromisoformat(date_event_str)
    except:
        return jsonify({"message": "Formato de fecha inválido"}), 400

    # Validar media
    if media and not media.startswith("http"):
        return jsonify({"message": "Media debe ser una URL válida"}), 400

    new_event = Event(
        name=name,
        location=location,
        lat=lat,
        lng=lng,
        description=description,
        date_event=date_event,
        capacity=capacity,
        media=media
    )
    if not promotor:
        return jsonify({"message": "Promotor no existe"}), 404

    db.session.add(new_event)
    db.session.flush()
    new_relation = EventPromotor(promotor_id=promotor_id, event_id=new_event.id)
    db.session.add(new_relation)
    db.session.commit()

    return jsonify({
        "message": "Evento creado correctamente",
        "new_event": new_event.serialize(),
        "promotor_relation": new_relation.serialize()
    }), 201


@promotor.route("/<int:promotor_id>/events/<int:event_id>", methods=["PUT"])
@jwt_required()
def update_event(promotor_id, event_id):
    if current_account_id() != promotor_id:
        return jsonify({"message": "No tienes permiso para modificar este evento"}), 403
    owns_event = db.session.execute(select(EventPromotor).where(
        EventPromotor.promotor_id == promotor_id,
        EventPromotor.event_id == event_id
    )).scalar_one_or_none()
    if owns_event is None:
        return jsonify({"message": "El evento no pertenece a este promotor"}), 403
    event = db.session.get(Event, event_id)

    if event is None:
        return jsonify({"message": "Evento no encontrado"}), 404

    body = request.get_json(silent=True)

    if body is None:
        return jsonify({"message": "Debes enviar un JSON válido"}), 400

    # CAMPOS NORMALES
    if "name" in body:
        event.name = body["name"]

    if "location" in body:
        event.location = body["location"]

    if "latitude" in body:
        event.lat = body["latitude"]
    
    if "longitude" in body:
        event.lng = body["longitude"]

    if "description" in body:
        event.description = body["description"]

    if "capacity" in body:
        event.capacity = body["capacity"]

    # FECHA
    if "date_event" in body:
        try:
            event.date_event = datetime.fromisoformat(body["date_event"])
        except:
            return jsonify({"message": "Formato de fecha inválido"}), 400

    # MEDIA
    if "media" in body:
        if body["media"] == "":
            event.media = None
        elif body["media"].startswith("http"):
            event.media = body["media"]
        else:
            return jsonify({"message": "Media debe ser una URL válida"}), 400

    db.session.commit()

    return jsonify({
        "message": "Evento actualizado correctamente",
        "results": event.serialize()
    }), 200


@promotor.route("/<int:promotor_id>/events/<int:event_id>", methods=["DELETE"])
@jwt_required()
def delete_event(promotor_id, event_id):
    if current_account_id() != promotor_id:
        return jsonify({"message": "No tienes permiso para eliminar este evento"}), 403
    owns_event = db.session.execute(select(EventPromotor).where(
        EventPromotor.promotor_id == promotor_id,
        EventPromotor.event_id == event_id
    )).scalar_one_or_none()
    if owns_event is None:
        return jsonify({"message": "El evento no pertenece a este promotor"}), 403
    event = db.session.get(Event, event_id)
    promotor = db.session.get(Promotor, promotor_id)

    if event is None:
        return jsonify({"message": "Evento no encontrado"}), 404

    promotorEvents = db.session.execute(select(EventPromotor).where(
        EventPromotor.event_id == event_id)).scalars().all()
    userEvents = db.session.execute(select(SavedEvent).where(
        SavedEvent.event_id == event_id)).scalars().all()
    userAssistEvents = db.session.execute(select(EventAssistUser).where(
        EventAssistUser.event_id == event_id)).scalars().all()
    categoryEvents = db.session.execute(select(EventCategory).where(
        EventCategory.event_id == event_id)).scalars().all()
    groupEvents = db.session.execute(select(GroupEvent).where(
        GroupEvent.event_id == event_id)).scalars().all()
    commentEvents = db.session.execute(select(Comment).where(
        Comment.event_id == event_id)).scalars().all()

    for item in promotorEvents:
        db.session.delete(item)
    for item in userEvents:
        db.session.delete(item)
    for item in userAssistEvents:
        db.session.delete(item)
    for item in categoryEvents:
        db.session.delete(item)
    for item in groupEvents:
        db.session.delete(item)
    for item in commentEvents:
        db.session.delete(item)

    db.session.delete(event)
    db.session.commit()

    return jsonify({
        "message": f"Succesfully deleted event with ID {event_id} for owner {promotor.name}"
    }), 200

# asignar categorias a los eventos creados por X promotor


@promotor.route('<int:promotor_id>/events/<int:event_id>/event_category', methods=['GET'])
@jwt_required()
def get_event_category(event_id,promotor_id):

    event = db.session.get(Event, event_id)
    eventCatRelation = db.session.execute(select(EventCategory).where(
        EventCategory.event_id == event_id)).scalars().all()

    for category in eventCatRelation:
        if category is None:
            return jsonify({"message": "No events found"}), 404

    return jsonify({
        "message": f"{len(eventCatRelation)} where found for event {event.name}",
        "eventCategories": list(map(lambda relation: relation.serialize(), eventCatRelation)),
    }), 200


@promotor.route('<int:promotor_id>/events/<int:event_id>/event_category', methods=['POST'])
@jwt_required()
def create_event_category(promotor_id, event_id):

    body = request.json
    if "event_id" not in body or "category_id" not in body:
        return jsonify("Please provide a event ID and a category ID"), 400

    if body["event_id"] == "" or body["category_id"] == "":
        return jsonify("Please provide a valid event and a category ID"), 400

    if db.session.execute(select(Event).where(Event.id == body["event_id"])).scalar_one_or_none() == None:
        return jsonify("The event does not exist"), 400

    if db.session.execute(select(Category).where(Category.id == body["category_id"])).scalar_one_or_none() == None:
        return jsonify("The category does not exist"), 400

    event_category = EventCategory(**body)

    db.session.add(event_category)
    db.session.commit()

    response_body = {
        "message": "The event category has been created correctly",
        "event_category": event_category.serialize()
    }

    return jsonify(response_body), 200

@promotor.route('<int:promotor_id>/events/<int:event_id>/event_category/<int:position>', methods=['DELETE'])
@jwt_required()
def delete_event_category_by_id(promotor_id, event_id ,position):

    event_category = db.session.get(EventCategory, position)

    if event_category == None:
        return jsonify("This event category does not exist"), 404

    db.session.delete(event_category)
    db.session.commit()

    response_body = {
        "message": "The event category has been deleted correctly",
        "event_category": event_category.serialize()
    }

    return jsonify(response_body), 200

# ver asistentes del evento creado por X promotor

@promotor.route("/events/<int:event_id>/event-assists", methods=["GET"])
@jwt_required()
def get_event_assists(event_id):

    event = db.session.get(Event, event_id)
    eventAsistRelation = db.session.execute(select(EventAssistUser).where(
        EventAssistUser.event_id == event_id)).scalars().all()


    return jsonify({
        "message": f"{len(eventAsistRelation)} where found for event {event.name}",
        "relations": list(map(lambda relation: relation.serialize(), eventAsistRelation)),}), 200


# comments on the event

@promotor.route('/events/<int:event_id>/comments', methods=['GET'])
@jwt_required()
def get_comments(event_id):

    event = db.session.get(Event, event_id)
    eventCommentRelation = db.session.execute(select(Comment).where(
        Comment.event_id == event_id)).scalars().all()

    for user in eventCommentRelation:
        if user is None:
            return jsonify({"message": "No comments found"}), 404
        
    return jsonify({
        "message": f"{len(eventCommentRelation)} where found for event {event.name}",
        "comments": list(map(lambda relation: relation.serialize(), eventCommentRelation))}), 200


@promotor.route('/events/<int:event_id>/comments/<int:id>', methods=['GET'])
@jwt_required()
def get_comment(event_id, id):
    comment = db.session.get(Comment, id)

    if comment is None:
        return jsonify({"msg": "Comment not found"}), 404
    
    if comment.event.id != event_id:
        return jsonify({"msg": "This comment is not on your event"}), 404

    return jsonify(comment.serialize()), 200

@promotor.route('/events/<int:event_id>/comments/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_comment(id, event_id):
    comment = db.session.get(Comment, id)

    if comment is None:
        return jsonify({"msg": "Comment not found"}), 404
    
    if comment.event.id != event_id:
        return jsonify({"msg": "This comment is not on your event"})

    db.session.delete(comment)
    db.session.commit()

    return jsonify({"msg": "Deleted"}), 200


def get_current_promotor():
    if current_role() != "promotor":
        return None
    return db.session.get(Promotor, current_account_id())

@promotor.route("/chats", methods=["GET"])
@jwt_required()
def get_promotor_chats():
    promotor = get_current_promotor()

    if promotor is None:
        return jsonify({"message": "Promotor no encontrado"}), 404

    chats = db.session.execute(
        select(Chat).where(Chat.promotor_id == promotor.id)
    ).scalars().all()

    return jsonify([chat.serialize() for chat in chats]), 200

@promotor.route("/chats/<int:chat_id>/messages", methods=["GET"])
@jwt_required()
def get_promotor_chat_messages(chat_id):
    promotor = get_current_promotor()

    if promotor is None:
        return jsonify({"message": "Promotor no encontrado"}), 404

    chat = db.session.get(Chat, chat_id)

    if chat is None:
        return jsonify({"message": "Chat no encontrado"}), 404

    if chat.promotor_id != promotor.id:
        return jsonify({"message": "No tienes permiso para este chat"}), 403

    messages = db.session.execute(
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(Message.created_at.asc())
    ).scalars().all()

    return jsonify([message.serialize() for message in messages]), 200

@promotor.route("/chats/<int:chat_id>/messages", methods=["POST"])
@jwt_required()
def create_promotor_chat_message(chat_id):
    promotor = get_current_promotor()

    if promotor is None:
        return jsonify({"message": "Promotor no encontrado"}), 404

    chat = db.session.get(Chat, chat_id)

    if chat is None:
        return jsonify({"message": "Chat no encontrado"}), 404

    if chat.promotor_id != promotor.id:
        return jsonify({"message": "No tienes permiso para este chat"}), 403

    data = request.get_json()
    text = data.get("text")

    if not text:
        return jsonify({"message": "text es requerido"}), 400

    message = Message(
        chat_id=chat.id,
        sender_type="promotor",
        sender_id=promotor.id,
        text=text
    )

    db.session.add(message)
    db.session.commit()

    return jsonify(message.serialize()), 201

