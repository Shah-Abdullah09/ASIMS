from django.http import FileResponse


def private_file(file, content_type, filename):
    """Stream a stored file to a user the caller has already checked. Files are never exposed by a public URL,
    and browsers and proxies are told not to keep a copy."""
    response = FileResponse(file.open('rb'), content_type=content_type, filename=filename, as_attachment=False)
    response['Cache-Control'] = 'private, no-store'
    return response
