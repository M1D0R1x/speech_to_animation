import json
import logging
import nltk
import re
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.staticfiles import finders
from django.http import JsonResponse
from django.shortcuts import render, redirect
from nltk.corpus import stopwords
from nltk.corpus import wordnet
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

try:
    with open(settings.SYNONYM_PATH, 'r', encoding='utf-8') as f:
        custom_synonyms = json.load(f)
except Exception as e:
    custom_synonyms = {}
    logging.error(f"Could not load synonyms.json: {e}")

# Logging
logger = logging.getLogger(__name__)

def home_view(request):
    return render(request, 'home.html')

def about_view(request):
    return render(request, 'about.html')

def contact_view(request):
    return render(request, 'contact.html')

# Load custom synonyms from synonyms.json
def load_custom_synonyms():
    """Loads custom synonym dictionary from a JSON file."""
    try:
        with open(settings.SYNONYM_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error("Error: synonyms.json not found.")
        return {}
    except json.JSONDecodeError:
        logger.error("Error: Invalid JSON format in synonyms.json.")
        return {}


custom_synonyms = load_custom_synonyms()

def find_synonym(word):
    """Finds synonyms of a word using Custom Dictionary first, then WordNet."""
    if word in custom_synonyms:
        return custom_synonyms[word]

    synonyms = []
    for syn in wordnet.synsets(word):
        for lemma in syn.lemmas():
            synonyms.append(lemma.name())

    return synonyms[0] if synonyms else None  # Return first synonym if exists


@login_required(login_url="login")
def animation_view(request):
    if request.method == 'POST':
        try:
            text = request.POST.get('sen')
            if not text:
                raise ValueError("No input text provided.")

            # Clean special characters using regex
            text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
            text = text.lower()
            words = word_tokenize(text)
            tagged = nltk.pos_tag(words)

            # Improved tense detection
            tense = {
                "future": 0,
                "present": 0,
                "past": 0,
                "present_continuous": 0,
            }
            for word, tag in tagged:
                if tag == "MD":
                    tense["future"] += 1
                elif tag in ["VBP", "VBZ"]:
                    tense["present"] += 1
                elif tag == "VBG":
                    tense["present_continuous"] += 1
                elif tag in ["VBD", "VBN"]:
                    tense["past"] += 1

            # Prioritize tense
            if tense["future"] > 0:
                probable_tense = "future"
            elif tense["present_continuous"] > 0 and tense["present"] > 0:
                probable_tense = "present_continuous"
            elif tense["past"] > 0:
                probable_tense = "past"
            else:
                probable_tense = "present"

            logger.info(f"Chosen Tense: {probable_tense}")

            # Filter and lemmatize words
            important_words = {"i", "he", "she", "they", "we", "what", "where", "how", "you", "your", "my", "name", "hear", "book", "sign", "me", "yes", "no", "not", "now", "before", "will"}
            stop_words = set(stopwords.words('english')) - important_words
            isl_replacements = {"i": "me"}
            lr = WordNetLemmatizer()

            filtered_words = []
            for word, tag in tagged:
                if word not in stop_words:
                    word = isl_replacements.get(word, word)
                    if tag in ['VBG', 'VBD', 'VBZ', 'VBN']:  # Lemmatize all verbs, including VBG
                        word = lr.lemmatize(word, pos='v')  # "eating" → "eat", "coming" → "come"
                    elif tag == 'NN':
                        word = lr.lemmatize(word, pos='n')
                    elif tag in ['JJ', 'JJR', 'JJS', 'RBR', 'RBS']:
                        word = lr.lemmatize(word, pos='a')
                    else:
                        word = lr.lemmatize(word)
                    filtered_words.append(word)

            # # Replace the tense insertion block in your function:
            # if probable_tense == "past" and "before" not in [w.lower() for w in filtered_words]:
            #     filtered_words.insert(0, "before")
            # elif probable_tense == "future" and "will" not in [w.lower() for w in filtered_words]:
            #     filtered_words.insert(0, "will")
            # elif probable_tense == "present_continuous" and "now" not in [w.lower() for w in filtered_words]:
            #     if filtered_words and filtered_words[0] == "me":
            #         filtered_words.insert(1, "now")  # "me now eat"
            #     else:
            #         filtered_words.insert(0, "now")
            # elif probable_tense == "present" and "now" not in [w.lower() for w in filtered_words]:
            #     if filtered_words and filtered_words[0] == "me":
            #         filtered_words.insert(1, "now")  # "me now tired"
            #     else:
            #         filtered_words.insert(0, "now")

            logger.info(f"Final Processed Words: {filtered_words}")
            words = filtered_words

            # Process words for animations
            synonym_mapping = {}
            processed_words = []
            for w in words:
                path = w + ".mp4"
                animation_path = finders.find(path)

                if animation_path:
                    processed_words.append(w)
                else:
                    synonym = find_synonym(w)
                    if synonym and finders.find(synonym + ".mp4"):
                        processed_words.append(synonym)
                        synonym_mapping[w] = synonym
                        logger.info(f"Using synonym '{synonym}' for '{w}'")
                    else:
                        logger.warning(f"No animation found for '{w}', breaking into letters.")
                        processed_words.extend(list(w))

            logger.info(f"Processed Words: {processed_words}")

            return render(request, 'animation.html', {
                'words': processed_words,
                'text': text,
                'synonym_mapping': synonym_mapping
            })

        except ValueError as ve:
            logger.error(f"ValueError: {ve}")
            return render(request, 'animation.html', {'error': str(ve)})

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return render(request, 'animation.html', {'error': "An unexpected error occurred."})

    return render(request, 'animation.html')



# Signup view
def signup_view(request):
    if request.method == 'POST':
        try:
            form = UserCreationForm(request.POST)
            if form.is_valid():
                user = form.save()
                login(request, user)
                return redirect('animation')
            else:
                return render(request, 'signup.html', {'form': form, 'error': "Invalid signup details."})
        except Exception as e:
            logger.error(f"Error during signup: {e}")
            return render(request, 'signup.html', {'form': UserCreationForm(), 'error': "An unexpected error occurred."})
    else:
        return render(request, 'signup.html', {'form': UserCreationForm()})

# Login view
def login_view(request):
    if request.method == 'POST':
        try:
            form = AuthenticationForm(data=request.POST)
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                if 'next' in request.POST:
                    return redirect(request.POST.get('next'))
                else:
                    return redirect('animation')
            else:
                return render(request, 'login.html', {'form': form, 'error': "Invalid login details."})
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return render(request, 'login.html', {'form': AuthenticationForm(), 'error': "An unexpected error occurred."})
    else:
        return render(request, 'login.html', {'form': AuthenticationForm()})

# Logout view
def logout_view(request):
    try:
        logout(request)
        return redirect("home")
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return redirect("home")

# Custom 404 error page
def error_404_view(request, exception):
    return render(request, '404.html', status=404)

# Custom 500 error page
def error_500_view(request):
    return render(request, '500.html', status=500)

# Check if animation exists
def check_animation(request, word):
    """Checks if an animation file exists for the given word."""
    path = word + ".mp4"
    file_exists = bool(finders.find(path))
    return JsonResponse({'word': word, 'exists': file_exists})