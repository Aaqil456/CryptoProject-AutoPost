jQuery(document).ready(function ($) {
  $('#dashboard').DataTable({
    ajax: {
      url: 'https://aaqil456.github.io/CryptoProject-AutoPost/dashboard.json',
      dataSrc: ''
    },
    columns: [
      { data: 'nama' },
      { data: 'dana' },
      { data: 'fasa' },
      { data: 'ada_token' },
      { data: 'pelabur' },
      { data: 'deskripsi' },
      {
        data: 'twitter',
        render: function(data) {
          if (!data || data === "-" || data.trim() === "") return "-";
          return '<a href="https://x.com/' + data.replace('@', '') + '" target="_blank">' + data + '</a>';
        }
      },
      {
        data: 'tweet_url',
        render: function(data) {
          return '<a href="' + data + '" target="_blank">🔗</a>';
        }
      }
    ],
    pageLength: 5,
    language: {
      search: "Cari Projek:",
      lengthMenu: "Papar _MENU_ entri",
      info: "Menunjukkan _START_ hingga _END_ dari _TOTAL_ entri",
      paginate: {
        previous: "Sebelum",
        next: "Seterusnya"
      }
    }
  });
});

