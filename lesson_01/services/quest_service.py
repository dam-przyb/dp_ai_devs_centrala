import csv
import requests
from pydantic import BaseModel, Field
from django.conf import settings
from langchain_openai import ChatOpenAI


# ── Pydantic Models ──────────────────────────────────────────────────────────


class Person(BaseModel):
    """CSV row representation"""
    name: str
    surname: str
    gender: str
    birthDate: str  # Birth date in format YYYY-MM-DD
    birthPlace: str
    job: str  # Job description text

    @property
    def birth_year(self) -> int:
        """Extract birth year from birthDate"""
        return int(self.birthDate.split('-')[0])


class JobTags(BaseModel):
    """LLM structured output for single job"""
    tags: list[str] = Field(
        description="Applicable tags: IT, transport, edukacja, medycyna, praca z ludźmi, praca z pojazdami, praca fizyczna"
    )


class PersonWithTags(BaseModel):
    """Person with assigned job tags"""
    name: str
    surname: str
    gender: str
    birthDate: str
    birthPlace: str
    job: str
    tags: list[str]

    @property
    def birth_year(self) -> int:
        """Extract birth year from birthDate"""
        return int(self.birthDate.split('-')[0])


class QuestResult(BaseModel):
    """Complete workflow result for UI display"""
    total_downloaded: int
    after_filter: int
    transport_workers: int
    submitted: list[PersonWithTags]
    flag: str
    error: str | None = None


# ── Service Functions ────────────────────────────────────────────────────────


def _get_llm():
    """Get configured LLM instance"""
    return ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )


def download_csv(api_key: str) -> list[Person]:
    """Download and parse people.csv from AG3NTS Hub"""
    url = f"https://hub.ag3nts.org/data/{api_key}/people.csv"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    # Parse CSV
    lines = response.text.strip().split('\n')
    reader = csv.DictReader(lines)

    people = []
    for row in reader:
        person = Person(
            name=row['name'],
            surname=row['surname'],
            gender=row['gender'],
            birthDate=row['birthDate'],
            birthPlace=row['birthPlace'],
            job=row['job']
        )
        people.append(person)

    return people


def filter_people(people: list[Person]) -> list[Person]:
    """Filter by demographics: Male, age 20-40 in 2026, born in Grudziądz"""
    filtered = []
    for person in people:
        # Calculate age in 2026
        age_in_2026 = 2026 - person.birth_year

        # Check all criteria
        is_male = person.gender.upper() == "M"
        is_correct_age = 20 <= age_in_2026 <= 40
        is_from_grudziadz = person.birthPlace.lower() == "grudziądz"

        if is_male and is_correct_age and is_from_grudziadz:
            filtered.append(person)

    return filtered


def tag_job(job_description: str) -> JobTags:
    """Use LLM to tag a single job description"""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(JobTags)

    prompt = f"""You are a job classifier. Given a job description, assign applicable tags from this list:

- IT: Information technology, programming, software development
- transport: Transportation, logistics, delivery, driving
- edukacja: Education, teaching, training
- medycyna: Medicine, healthcare, nursing, doctors
- praca z ludźmi: Working with people, customer service, social work
- praca z pojazdami: Working with vehicles, mechanics, car repair
- praca fizyczna: Physical labor, construction, manual work

A job can have multiple tags. Return only the applicable tags.

Job description: {job_description}"""

    return structured_llm.invoke(prompt)


def tag_all_jobs(people: list[Person]) -> list[PersonWithTags]:
    """Tag all jobs for filtered people"""
    tagged_people = []

    for person in people:
        job_tags = tag_job(person.job)

        person_with_tags = PersonWithTags(
            name=person.name,
            surname=person.surname,
            gender=person.gender,
            birthDate=person.birthDate,
            birthPlace=person.birthPlace,
            job=person.job,
            tags=job_tags.tags
        )
        tagged_people.append(person_with_tags)

    return tagged_people


def select_transport_people(tagged_people: list[PersonWithTags]) -> list[PersonWithTags]:
    """Filter people with 'transport' tag"""
    return [person for person in tagged_people if "transport" in person.tags]


def submit_to_verify(api_key: str, people: list[PersonWithTags]) -> dict:
    """Submit results to verify endpoint"""
    # Build payload
    answer = []
    for person in people:
        answer.append({
            "name": person.name,
            "surname": person.surname,
            "gender": person.gender,
            "born": person.birth_year,  # Extract year from birthDate
            "city": person.birthPlace,  # Use birthPlace as city
            "tags": person.tags
        })

    payload = {
        "apikey": api_key,
        "task": "people",
        "answer": answer
    }

    # Submit to hub
    response = requests.post(
        "https://hub.ag3nts.org/verify",
        json=payload,
        timeout=30
    )
    response.raise_for_status()

    return response.json()


def execute_quest(api_key: str) -> QuestResult:
    """Execute complete quest workflow with step tracking"""
    try:
        # Step 1: Download CSV
        people = download_csv(api_key)
        total_downloaded = len(people)

        # Step 2: Filter people
        filtered_people = filter_people(people)
        after_filter = len(filtered_people)

        # Step 3: Tag jobs
        tagged_people = tag_all_jobs(filtered_people)

        # Step 4: Select transport workers
        transport_people = select_transport_people(tagged_people)
        transport_workers = len(transport_people)

        # Step 5: Submit to verify
        verify_response = submit_to_verify(api_key, transport_people)

        # Extract flag from response
        flag = verify_response.get("flag", verify_response.get("message", str(verify_response)))

        return QuestResult(
            total_downloaded=total_downloaded,
            after_filter=after_filter,
            transport_workers=transport_workers,
            submitted=transport_people,
            flag=flag,
            error=None
        )

    except Exception as exc:
        return QuestResult(
            total_downloaded=0,
            after_filter=0,
            transport_workers=0,
            submitted=[],
            flag="",
            error=str(exc)
        )
