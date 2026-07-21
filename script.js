<script>
function getSelectedCheckboxes(name) {
    const checkboxes = document.querySelectorAll('input[name="' + name + '"]:checked');
    const selectedValues = Array.from(checkboxes).map(checkbox => checkbox.value);
    const otherInput = document.getElementById(name + "OtherText");
    const otherText = otherInput.value.trim();
    if (otherText !== "") {
        selectedValues.push(otherText);
    }
    return selectedValues.join(', ');
}
</script>