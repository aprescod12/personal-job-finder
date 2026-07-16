from django.shortcuts import get_object_or_404, redirect, render

from .forms import JobPostingForm
from .models import JobPosting


def job_list(request):
    jobs = JobPosting.objects.all()

    return render(
        request,
        "tracker/job_list.html",
        {"jobs": jobs},
    )

def job_detail(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)

    return render(
        request,
        "tracker/job_detail.html",
        {"job": job},
    )

def job_create(request):
    if request.method == "POST":
        form = JobPostingForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("job_list")
    else:
        form = JobPostingForm()

    return render(
        request,
        "tracker/job_form.html",
        {"form": form},
    )