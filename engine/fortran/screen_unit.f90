! One work unit of the catalogue screening (engine/screen.py): two-body positions, Izzo Lambert (single revolution, prograde),
! pricing and the cheapest transfer overall and per calendar year, for every object, hub and direction.
! Usage: screen_unit hubs.bin input.bin output.bin
! hubs.bin:   states [6, n_t, n_hub] (m, m/s), written once per run by engine/screen.py
! input.bin:  int32 header n, n_dep, n_t, n_hub, n_tof, n_years; real64 jd0, step, mu_sun, day_s, au_m, k_gauss;
!             real64 parking mu [n_hub], parking r [n_hub]; int32 year index [n_dep]; real64 elements [n, 7] (a e i om w ma epoch);
!             int32 flight steps [n_tof, n_hub, n] (0 = unused)
! output.bin: real64 best [5, 2, n_hub, n] (cost, departure step, flight steps, vinf_dep, vinf_arr; NaN if none);
!             real32 year minimum [n_years, 2, n_hub, n] (NaN if none)
program screen_unit
  use iso_fortran_env, only: real64, real32, int32
  use, intrinsic :: ieee_arithmetic, only: ieee_value, ieee_quiet_nan, ieee_is_finite
  use lambert_izzo, only: solve_lambert_izzo
  implicit none
  integer, parameter :: wp = real64
  integer(int32) :: hdr(6)
  integer :: n, n_dep, n_t, n_hub, n_tof, n_years, u, o, h, d, k, j, s, ns, ky, jb
  real(wp) :: p(6), jd0, step, mu_sun, day_s, au_m, k_gauss, nan, rate
  real(wp), allocatable :: hubs(:,:,:), mu(:), rp(:), el(:,:), best(:,:,:,:), ro(:,:), vo(:,:), v1(:,:), v2(:,:)
  real(real32), allocatable :: ymin(:,:,:,:)
  integer(int32), allocatable :: years(:), steps(:,:,:)
  real(wp) :: c, cb, vd, va, vdb, vab, overall, r1(3), r2(3), w1(3), w2(3), tof
  real(real32) :: cf
  character(len=512) :: fhub, fin, fout
  logical :: ok, lw, fin_o
  call get_command_argument(1, fhub); call get_command_argument(2, fin); call get_command_argument(3, fout)
  open(newunit=u, file=fin, access='stream', form='unformatted', status='old')
  read(u) hdr; n = hdr(1); n_dep = hdr(2); n_t = hdr(3); n_hub = hdr(4); n_tof = hdr(5); n_years = hdr(6)
  read(u) p; jd0 = p(1); step = p(2); mu_sun = p(3); day_s = p(4); au_m = p(5); k_gauss = p(6)
  allocate(mu(n_hub), rp(n_hub), years(n_dep), el(n, 7), steps(n_tof, n_hub, n))
  read(u) mu, rp, years, el, steps
  close(u)
  allocate(hubs(6, n_t, n_hub), best(5, 2, n_hub, n), ymin(n_years, 2, n_hub, n), ro(3, n_t), vo(3, n_t))
  open(newunit=u, file=fhub, access='stream', form='unformatted', status='old'); read(u) hubs; close(u)
  nan = ieee_value(1.0_wp, ieee_quiet_nan); best = nan; ymin = huge(1.0_real32)
  do o = 1, n
    call two_body(el(o, :), ro, vo, fin_o)
    if (.not. fin_o) cycle
    do h = 1, n_hub
      ns = count(steps(:, h, o) > 0); if (ns == 0) cycle
      do d = 1, 2                                  ! 1: hub to object, 2: object to hub
        overall = huge(1.0_wp)
        do k = 1, n_dep
          cb = huge(1.0_wp); jb = 0; vdb = nan; vab = nan
          do j = 1, ns
            s = steps(j, h, o); tof = s * step * day_s
            if (d == 1) then
              r1 = hubs(1:3, k, h); r2 = ro(:, k + s)
            else
              r1 = ro(:, k); r2 = hubs(1:3, k + s, h)
            end if
            lw = r1(1) * r2(2) - r1(2) * r2(1) < 0.0_wp
            call solve_lambert_izzo(r1, r2, tof, mu_sun, lw, 0, v1, v2, ok)
            if (.not. ok) cycle
            if (d == 1) then
              w1 = hubs(4:6, k, h); w2 = vo(:, k + s)
            else
              w1 = vo(:, k); w2 = hubs(4:6, k + s, h)
            end if
            vd = norm2(v1(:, 1) - w1) / 1000.0_wp; va = norm2(v2(:, 1) - w2) / 1000.0_wp
            if (d == 1) then
              c = burn(vd, mu(h), rp(h)) + va
            else
              c = vd + burn(va, mu(h), rp(h))
            end if
            if (ieee_is_finite(c) .and. c < cb) then
              cb = c; jb = j; vdb = vd; vab = va
            end if
          end do
          if (jb == 0) cycle
          cf = real(cb, real32); ky = years(k) + 1
          if (cf < ymin(ky, d, h, o)) ymin(ky, d, h, o) = cf
          if (cb < overall) then
            overall = cb
            best(:, d, h, o) = [cb, real(k - 1, wp), real(steps(jb, h, o), wp), vdb, vab]
          end if
        end do
      end do
    end do
  end do
  where (ymin == huge(1.0_real32)) ymin = real(nan, real32)
  open(newunit=u, file=fout, access='stream', form='unformatted', status='replace'); write(u) best, ymin; close(u)
contains
  pure real(wp) function burn(v, m, r)
    real(wp), intent(in) :: v, m, r
    if (m > 0.0_wp) then
      burn = sqrt(v * v + 2.0_wp * m / r) - sqrt(m / r)
    else
      burn = v
    end if
  end function
  subroutine two_body(e, r, v, finite)                 ! engine/screen.py two_body_states, one object
    real(wp), intent(in) :: e(7)
    real(wp), intent(out) :: r(:,:), v(:,:)
    logical, intent(out) :: finite
    real(wp) :: a, ec, nm, b, PP(3), QQ(3), ci, si, co, so, cw, sw, jd, MM, EE, ce, se, de, xp, yp, vx, vy, deg, pi_, lo, hi, ff, nw
    integer :: t, it
    pi_ = acos(-1.0_wp); deg = pi_ / 180.0_wp
    a = e(1); ec = e(2); nm = k_gauss * a ** (-1.5_wp); b = a * sqrt(1.0_wp - ec * ec)
    ci = cos(e(3) * deg); si = sin(e(3) * deg); co = cos(e(4) * deg); so = sin(e(4) * deg); cw = cos(e(5) * deg); sw = sin(e(5) * deg)
    PP = [co * cw - so * sw * ci, so * cw + co * sw * ci, sw * si]
    QQ = [-co * sw - so * cw * ci, -so * sw + co * cw * ci, cw * si]
    finite = .true.
    do t = 1, size(r, 2)
      jd = jd0 + step * (t - 1)
      MM = modulo(e(6) * deg + nm * (jd - e(7)) + pi_, 2.0_wp * pi_) - pi_
      lo = -pi_; hi = pi_; EE = MM                      ! Newton kept inside a bracket: plain Newton diverges above e = 0.97
      if (ec > 0.8_wp) EE = merge(-pi_, pi_, MM < 0.0_wp)
      do it = 1, 60
        ff = EE - ec * sin(EE) - MM
        if (ff > 0.0_wp) then
          hi = EE
        else
          lo = EE
        end if
        nw = EE - ff / (1.0_wp - ec * cos(EE))
        if (.not. (nw > lo .and. nw < hi)) nw = 0.5_wp * (lo + hi)
        if (abs(nw - EE) < 1.0e-14_wp) then
          EE = nw; exit
        end if
        EE = nw
      end do
      ce = cos(EE); se = sin(EE); de = 1.0_wp - ec * ce
      xp = a * (ce - ec); yp = b * se; vx = -a * nm * se / de; vy = b * nm * ce / de
      r(:, t) = (xp * PP + yp * QQ) * au_m; v(:, t) = (vx * PP + vy * QQ) * au_m / day_s
      if (.not. all(ieee_is_finite(r(:, t)))) finite = .false.
    end do
  end subroutine
end program
