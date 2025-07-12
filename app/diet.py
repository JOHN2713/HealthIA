import pandas as pd
import pulp
import google.generativeai as genai
from flask import current_app
import random
from config import Config
# Elegir imágenes aleatorias
imagen_desayuno = f"/static/img/desayuno{random.randint(1,4)}.jpg"
imagen_almuerzo = f"/static/img/almuerzo{random.randint(1,4)}.jpg"
imagen_cena = f"/static/img/cena{random.randint(1,4)}.jpg"
imagen_snack = f"/static/img/snack{random.randint(1,4)}.jpg"

# Configurar Gemini (reemplaza tu API key o usa .env)
genai.configure(api_key=Config.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# 1. Leer archivo CSV de alimentos
def load_foods(path="alimentos.csv"):
    df = pd.read_csv(path)
    df = df[df["calories"] >= 10]
    df = df[(df['protein'] > 0) | (df['fat'] > 0) | (df['carbs'] > 0)]

    df[['protein', 'carbs', 'fat', 'calories', 'cost']] = df[['protein', 'carbs', 'fat', 'calories', 'cost']].astype(float)

    # ✅ Estructura 1: Plano para LP
    foods_lp = {
        row['nombre']: {
            'protein': row['protein'],
            'carbs': row['carbs'],
            'fat': row['fat'],
            'calories': row['calories'],
            'cost': row['cost']
        }
        for _, row in df.iterrows()
    }

    # ✅ Diccionario agrupado por categoría para el frontend
    agrupados = {}
    for _, row in df.iterrows():
        categoria = row['categoría'].strip().lower()
        nombre = row['nombre']
        if categoria not in agrupados:
            agrupados[categoria] = []
        agrupados[categoria].append(nombre)

    return foods_lp, agrupados

# 2. Calcular TDEE y metas
def calculate_targets(weight, height, age, gender, objective):
    if gender.lower() == 'masculino':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    tdee = bmr * 1.2  # Actividad ligera

    if objective == "Perder peso":
        calorie_goal = tdee - 500
    elif objective == "Ganar masa":
        calorie_goal = tdee + 300
    else:
        calorie_goal = tdee

    protein = weight * 1.6
    fat = calorie_goal * 0.25 / 9
    carbs = (calorie_goal - protein * 4 - fat * 9) / 4

    return {
        "calories": calorie_goal,
        "protein": protein,
        "fat": fat,
        "carbs": carbs
    }

# 3. Resolver dieta con programación lineal
def solve_diet_lp(foods, targets, budget=None, banned_foods=None):
    if banned_foods is None:
        banned_foods = []

    penalizados = ["Azúcar Blanca", "Aceite de Girasol", "Ajo", "Mantequilla", "Margarina"]
    for item in penalizados:
        if item in foods:
            foods[item]["cost"] *= 20

    saludables = ["Seitán", "Bacalao Seco", "Clorella", "Espirulina",
                  "Levadura de Cerveza", "Pechuga de Pavo", "Pulpo", "Anchoas", "Jamón Serrano",
                  "Mozzarella", "Emmental", "Germen de Trigo", "Bisonte"]
    for item in saludables:
        if item in foods:
            foods[item]["cost"] *= 0.7

    prob = pulp.LpProblem("DietPlan", pulp.LpMinimize)
    x = pulp.LpVariable.dicts("portion", foods.keys(), lowBound=0)

    prob += pulp.lpSum([foods[f]['cost'] * x[f] for f in foods])
    prob += pulp.lpSum([foods[f]['protein'] * x[f] for f in foods]) >= targets['protein']
    prob += pulp.lpSum([foods[f]['fat'] * x[f] for f in foods]) >= targets['fat']
    prob += pulp.lpSum([foods[f]['carbs'] * x[f] for f in foods]) >= targets['carbs']
    prob += pulp.lpSum([foods[f]['calories'] * x[f] for f in foods]) >= targets['calories']

    total_portions = pulp.lpSum([x[f] for f in foods])
    for f in foods:
        prob += x[f] <= 0.3 * total_portions

    prob += pulp.lpSum([x[f] >= 0.05 for f in foods]) >= 5

    for bf in banned_foods:
        if bf in x:
            prob += x[bf] == 0

    if budget:
        prob += pulp.lpSum([foods[f]['cost'] * x[f] for f in foods]) <= budget

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    solution = {f: x[f].value() or 0 for f in foods}
    total = sum(solution.values())
    proportions = {f: (solution[f]/total*100 if total > 0 else 0) for f in foods}
    return proportions, solution

# 4. Generar menú con Gemini
def generate_menu(proportions, user_data, days):
    objetivo = user_data.get("objective") 
    alimentos_utilizados = {
        k: v for k, v in proportions.items()
        if v > 0 and v >= 1  # al menos 1% del total
    }

    prompt = f"""
Genera un menú alimenticio para {days} día(s), con las siguientes características:

🔸 El objetivo del menú es: **{objetivo}**. Incluye una breve explicación del objetivo en una sección con subtítulo <h3>.

🔸 Incluye cuatro comidas diarias: **Desayuno**, **Almuerzo**, **Cena** y **Snack**. Para cada una:
🔸 Usa estos alimentos y proporciones: {alimentos_utilizados}.
- Usa subtítulos <h3> con el nombre de la comida.
- Incluye el **nombre del plato en negrita** y una lista ordenada (<ol>) con los ingredientes.
- Los encabezados de las tablas deben tener fondo verde (#a3d9a5) o amarillo suave (#f4d35e) para destacar, con texto oscuro.
- Muestra para cada ingrediente su **porcentaje aproximado y porción sugerida**

🔸 Diseño tipo infografía:
usa en el html <meta charset="utf-8">
- Organiza las comidas dentro de una cuadrícula 2x2, como un esquema visual de dieta (tipo Canva) para todos los {days} días.
- Usa un contenedor <div class="grid-dieta"> con bloques .comida.
- Cada bloque debe tener un color pastel diferente, borde redondeado, sombra suave y buena separación.
- Dentro de cada bloque, incluye: plato, título, ingredientes, porcentaje y, 
 usa imagenes como desayuno1.jpg, almuerzo1.jpg, cena1.jpg, snack1.jpg que estan en la ruta **<img src="file:///C:/Users/User/Desktop/diet_planner/static/img/** .
<img src="{imagen_desayuno}" alt="Desayuno" style="width: 50%; height: auto;">
<img src="{imagen_almuerzo}" alt="Almuerzo" style="width: 50%; height: auto;">
<img src="{imagen_cena}" alt="Cena" style="width: 50%; height: auto;">
<img src="{imagen_snack}" alt="Snack" style="width: 50%; height: auto;">

🔸 Estilo y compatibilidad:
- Devuelve todo el contenido en HTML con un bloque <style> interno donde ya se incluya la librería <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" integrity="sha512-DPZZn1PZ/F6h+l5EV8LLbM3X5B6BvFxjB54N7uD+1RE4G7DrBt7KMIWffzZqRX7bwomfqBIsK12ohWFXtTrZBw==" crossorigin="anonymous" referrerpolicy="no-referrer" />.
- un css table con:
    table-layout: fixed;
    word-wrap: break-word;
- Usa estilos modernos: colores suaves, tipografía clara, diseño responsivo (uso de grid o media queries).
- Compatible para dispositivos móviles y visualmente atractivo.
- Evita recomendaciones técnicas, librerías o etiquetas técnicas en el contenido.

🔸 Línea de tiempo:
- Añade una línea de tiempo visual <div class="timeline" style="border-left: 3px solid #ccc; padding-left: 10px; margin-left: 20px;"> al final con íconos y bloques verticales conectados por líneas.
- Ordena las comidas cronológicamente con breve recomendación en cada paso.

🔸 Nota final:
Incluye una breve nota que diga: “*Las proporciones son aproximadas. Se recomienda consultar con un profesional de la salud o nutrición para adaptaciones específicas.*”


{f"""
🔸 Además, genera una sección adicional con subtítulo <h3> llamada '🏋️ Rutina de ejercicios recomendada':
- Incluye 3 ejercicios diarios para cada {days} día del menú, separados por día.
- Agrega íconos, colores y estilo visual atractivo.
- Indica duración, repeticiones y si es para casa o al aire libre.
""" if user_data.get("rutina") else ""}
🔸 Asegúrate de que todo esté dentro de un único bloque HTML (con <html>, <head>, <body>) - Evita recomendaciones técnicas, librerías o etiquetas de rutas en el contenido.
"""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"⚠️ Error al generar menú: {e}"

# 5. Costo total
def calcular_costo_total(solution, foods):
    return sum(foods[f]["cost"] * qty for f, qty in solution.items())
